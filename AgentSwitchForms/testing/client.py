"""
MCP and REST test client for Seat 25 (Forms).
Supports live JSON-RPC calls against AgentSwitch and offline schema-validated dry runs.
Handles credentials securely without logging or printing tokens.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, Optional
from .validator import SchemaValidator

class FormsTestClient:
    """Test client to invoke Seat 25 MCP tools and REST endpoints."""

    def __init__(self, offline: Optional[bool] = None):
        self.validator = SchemaValidator()
        self._base_url = os.environ.get("AS")
        self._token = os.environ.get("TOKEN")

        if offline is not None:
            self.offline = offline
        else:
            self.offline = not (bool(self._base_url) and bool(self._token))

    def is_live(self) -> bool:
        return not self.offline

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args = arguments or {}

        # 1. Enforce seat boundaries
        if not self.validator.is_in_seat_boundary(name):
            return {
                "is_error": True,
                "error": {
                    "code": 403,
                    "message": f"Forbidden: Seat 25 (forms) does not hold authorization for tool or entity '{name}'."
                }
            }

        # 2. Check schema validity
        is_valid, validation_err = self.validator.validate_input(name, args)
        if not is_valid:
            return {
                "is_error": True,
                "error": {
                    "code": 400,
                    "message": f"Schema Validation Failed: {validation_err}"
                }
            }

        # 3. Dry-run mock if offline
        if self.offline:
            return self._mock_tool_response(name, args)

        # 4. Live MCP JSON-RPC call
        return self._execute_mcp_call(name, args)

    def _execute_mcp_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self._base_url or not self._token:
            return {"is_error": True, "error": {"code": 500, "message": "Missing environment credentials."}}

        url = f"{self._base_url.rstrip('/')}/api/mcp"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json"
        }
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments}
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "error" in data:
                    return {"is_error": True, "error": data["error"]}
                result = data.get("result", {})
                return {"is_error": result.get("isError", False), "result": result}
        except urllib.error.HTTPError as http_err:
            try:
                err_body = json.loads(http_err.read().decode("utf-8"))
            except Exception:
                err_body = {"code": http_err.code, "message": http_err.reason}
            return {"is_error": True, "error": err_body}
        except Exception as e:
            return {"is_error": True, "error": {"code": 500, "message": str(e)}}

    def api_get(self, path: str) -> Dict[str, Any]:
        clean_path = path.strip("/")
        # Cross-seat privacy boundary check: Forms seat cannot read Payroll messages or records
        if any(forbidden in clean_path.lower() for forbidden in ["payroll", "salaryslip", "payrollentry", "contract", "esigndocument"]):
            return {
                "status": "error",
                "is_error": True,
                "error": {
                    "code": 403,
                    "message": f"Forbidden: Seat 25 (forms) does not hold authorization to access '{path}' owned by Payroll."
                }
            }

        if self.offline:
            return {"status": "success", "result": {"offline": True, "path": path}}

        url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return {"status": "success", "result": json.loads(resp.read().decode("utf-8"))}
        except urllib.error.HTTPError as http_err:
            try:
                err_body = json.loads(http_err.read().decode("utf-8"))
            except Exception:
                err_body = {"code": http_err.code, "message": http_err.reason}
            return {"status": "error", "is_error": True, "error": err_body}
        except Exception as e:
            return {"status": "error", "is_error": True, "error": {"code": 500, "message": str(e)}}

    def _mock_tool_response(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "endpoint.storefront.locale":
            return {"is_error": False, "result": {"country_code": "IN", "currency_code": "INR", "tax_regime": "GST", "accounting_standard": "Ind AS"}}
        if name == "Form.create":
            return {"is_error": False, "result": {"id": "form_sub_onb_001", "name": args.get("name"), "status": "draft"}}
        if name in ["Form.update", "Form.get"]:
            return {
                "is_error": False,
                "result": {
                    "id": args.get("id", "form_sub_onb_001"),
                    "name": args.get("name", "Supplier Onboarding & Compliance Intake - 2026"),
                    "status": args.get("status", "published"),
                    "blocks": args.get("blocks", []),
                    "consent_required": True,
                    "consent_lawful_basis": "consent"
                }
            }
        if name == "AgentPersona.list":
            return {
                "is_error": False,
                "result": {
                    "data": [{"id": "persona_forms_001", "name": "Forms Agent", "is_active": True}],
                    "total": 1,
                    "limit": 20,
                    "offset": 0
                }
            }
        if name == "AgentSession.list":
            return {
                "is_error": False,
                "result": {
                    "data": [
                        {
                            "id": "ses_chat_ui_001",
                            "title": "Supplier Intake Chat",
                            "persona_id": "persona_forms_001",
                            "channel": "web",
                            "status": "active",
                            "last_message_at": "2026-09-27T10:00:00Z"
                        }
                    ],
                    "total": 1,
                    "limit": 20,
                    "offset": 0
                }
            }
        if name == "AgentSession.get":
            return {
                "is_error": False,
                "result": {
                    "id": args.get("id", "ses_chat_ui_001"),
                    "title": "Supplier Intake Chat",
                    "channel": "web",
                    "status": "active"
                }
            }
        if name == "AgentMessage.list":
            return {
                "is_error": False,
                "result": {
                    "data": [
                        {
                            "id": "msg_user_001",
                            "session_id": args.get("session_id", "ses_chat_ui_001"),
                            "role": "user",
                            "content": "Build and publish our supplier onboarding form with compliance consent."
                        }
                    ],
                    "total": 1,
                    "limit": 20,
                    "offset": 0
                }
            }
        if name == "AgentMessage.get":
            msg_id = str(args.get("id", ""))
            if "payroll" in msg_id.lower():
                return {
                    "is_error": True,
                    "error": {
                        "code": 403,
                        "message": f"Forbidden: Seat 25 (forms) cannot read private chat message '{msg_id}' belonging to Payroll seat."
                    }
                }
            return {
                "is_error": False,
                "result": {
                    "id": msg_id,
                    "session_id": "ses_chat_ui_001",
                    "role": "user",
                    "content": "Build and publish our supplier onboarding form with compliance consent."
                }
            }
        if name == "Party.create":
            return {"is_error": False, "result": {"id": "pty_vnd_987654", "name": args.get("name")}}
        return {"is_error": False, "result": {"status": "success", "mock": True, "tool": name}}
