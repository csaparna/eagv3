"""
Schema validator and seat boundary checker for Seat 25 (Forms).
Validates MCP tool arguments against official platform schemas and verifies security boundaries.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import jsonschema

BASE_DIR = Path(__file__).parent.parent

class SchemaValidator:
    """Validates inputs, outputs, and seat permissions for Seat 25 MCP tools."""

    def __init__(self, mcp_tools_path: Optional[Path] = None, seat_info_path: Optional[Path] = None):
        self.mcp_tools_path = mcp_tools_path or (BASE_DIR / "mcp_tools.json")
        self.seat_info_path = seat_info_path or (BASE_DIR / "seat_info.json")

        self.tools: Dict[str, Dict[str, Any]] = {}
        self.seat_info: Dict[str, Any] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        if self.mcp_tools_path.exists():
            with open(self.mcp_tools_path, "r", encoding="utf-8") as f:
                tools_list = json.load(f)
                self.tools = {t["name"]: t for t in tools_list}
        
        if self.seat_info_path.exists():
            with open(self.seat_info_path, "r", encoding="utf-8") as f:
                self.seat_info = json.load(f)

    def tool_exists(self, tool_name: str) -> bool:
        """Returns True if the tool is registered in Seat 25's tool definitions."""
        return tool_name in self.tools

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Returns the JSON Schema for the tool's input."""
        tool = self.tools.get(tool_name)
        if not tool:
            return None
        return tool.get("inputSchema")

    def validate_input(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validates argument dictionary against tool's JSON Schema.
        Returns (is_valid, error_message).
        """
        if not self.tool_exists(tool_name):
            return False, f"Tool '{tool_name}' does not exist in Seat 25 tool registry."

        schema = self.get_tool_schema(tool_name)
        if not schema:
            return True, None

        try:
            jsonschema.validate(instance=arguments, schema=schema)
            return True, None
        except jsonschema.ValidationError as err:
            return False, f"Schema validation error for '{tool_name}': {err.message} at path: {'/'.join(str(p) for p in err.path)}"

    def is_in_seat_boundary(self, tool_name: str) -> bool:
        """
        Checks whether the tool is within Seat 25's allowed domains (forms, crm, agent).
        Returns False for unauthorized domains (e.g. Payroll, Contracts, General Ledger).
        """
        # Explicit forbidden cross-seat entities
        forbidden_keywords = ["SalarySlip", "PayrollEntry", "Contract", "EsignDocument", "JournalEntry", "AssetScanEvent"]
        for kw in forbidden_keywords:
            if kw.lower() in tool_name.lower():
                return False

        if tool_name in self.tools:
            return True

        # Check domain in metadata if available
        tool = self.tools.get(tool_name, {})
        agentswitch_meta = tool.get("_meta", {}).get("agentswitch", {})
        path = agentswitch_meta.get("path", "")
        allowed_apps = self.seat_info.get("allowed_apps", ["forms", "crm", "agent"])
        
        return any(f"/api/{app}" in path for app in allowed_apps)

    def check_known_defects(self, tool_name: str, endpoint_path: str = "") -> Optional[str]:
        """
        Flags documented system bugs or architectural defects.
        """
        if "survey/analytics" in endpoint_path or "analytics" in tool_name:
            return (
                "KNOWN DEFECT (Gap 1.4 / Assignment §10): 'GET /api/survey/analytics/{id}' crashes with HTTP 500 "
                "due to querying nonexistent database tables. Use client-side aggregation over 'FormResponse.list' instead."
            )
        return None
