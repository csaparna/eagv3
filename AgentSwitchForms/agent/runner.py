"""
Forms Agent Execution Runner (Seat 25).
Executes the UC-01 task graph against AgentSwitch via MCP, records event traces,
and updates UI chat bot sessions or local UI dashboards.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from testing.client import FormsTestClient
from .chat_listener import UIChatListener
from .planner import AgentPlan, FormsTaskPlanner
from .schema_builder import FormSchemaBuilder


class FormsAgentRunner:
    """Executes natural language prompts through task graphs against AgentSwitch."""

    def __init__(self, client: Optional[FormsTestClient] = None):
        self.client = client or FormsTestClient()
        self.planner = FormsTaskPlanner()
        self.chat_listener = UIChatListener(self.client)

    def execute_prompt(self, prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        plan = self.planner.plan(prompt)

        # Handle Refusals (§3, §8)
        if plan.is_refusal:
            refusal_msg = plan.refusal_reason or "Request refused due to authorization boundary."
            if session_id:
                self.chat_listener.reply_to_session(session_id, refusal_msg, tool_status="refused")
            return {"success": False, "is_refusal": True, "prompt": prompt, "reply": refusal_msg, "nodes": []}

        locale_data: Dict[str, Any] = {}
        synthesized_form: Dict[str, Any] = {}
        created_form_id: Optional[str] = None
        event_log: List[Dict[str, Any]] = []

        for node in plan.nodes:
            node.state = "running"
            if node.node_id == "step_1_1_locale":
                res = self.client.call_tool("endpoint.storefront.locale", {})
                if res.get("is_error"):
                    node.state = "failed"
                    node.error = str(res.get("error"))
                    break
                res_obj = res.get("result", {})
                locale_data = res_obj.copy() if isinstance(res_obj, dict) else {}
                if isinstance(res_obj.get("data"), dict):
                    locale_data.update(res_obj["data"])
                node.result = locale_data
                node.state = "success"

            elif node.node_id == "step_1_2_synthesize":
                title = node.arguments.get("title")
                slug = node.arguments.get("slug")
                synthesized_form = FormSchemaBuilder.build_supplier_onboarding_form(locale_data, title, slug)
                node.result = {"title": synthesized_form["name"], "block_count": len(synthesized_form.get("blocks", []))}
                node.state = "success"

            elif node.node_id == "step_1_3_create_draft":
                res = self.client.call_tool("Form.create", synthesized_form)
                if res.get("is_error"):
                    node.state = "failed"
                    node.error = str(res.get("error"))
                    break
                res_obj = res.get("result", {})
                created_form_id = None
                if isinstance(res_obj, dict):
                    created_form_id = res_obj.get("id")
                    if not created_form_id and isinstance(res_obj.get("data"), dict):
                        created_form_id = res_obj["data"].get("id")
                    if not created_form_id and "content" in res_obj:
                        for c in res_obj.get("content", []):
                            try:
                                d = json.loads(c.get("text", ""))
                                if isinstance(d, dict):
                                    created_form_id = d.get("id") or (d.get("data", {}).get("id") if isinstance(d.get("data"), dict) else None)
                                    if created_form_id:
                                        break
                            except Exception:
                                pass
                if not created_form_id:
                    node.state = "failed"
                    node.error = f"Form.create succeeded but could not extract form ID: {res_obj}"
                    break
                node.result = res_obj
                node.state = "success"

            elif node.node_id == "step_1_4_publish":
                res = self.client.call_tool("Form.update", {"id": created_form_id, "status": "published"})
                if res.get("is_error"):
                    node.state = "failed"
                    node.error = str(res.get("error"))
                    break
                node.result = res.get("result")
                node.state = "success"

            elif node.node_id == "step_1_5_verify":
                res = self.client.call_tool("Form.get", {"id": created_form_id})
                if res.get("is_error"):
                    node.state = "failed"
                    node.error = str(res.get("error"))
                    break
                node.result = res.get("result")
                node.state = "success"

            event_log.append({"node_id": node.node_id, "tool": node.tool_name, "state": node.state})

        all_success = all(n.state == "success" for n in plan.nodes)
        form_name = synthesized_form.get("name", "Supplier Onboarding Form")
        form_slug = synthesized_form.get("slug", "supplier-onboarding")
        as_base = (os.environ.get("AGENTSWITCH_BASE_URL") or os.environ.get("AS") or "https://agentswitch.theschoolofai.in").rstrip("/")
        ui_link = f"{as_base}/p/form/{form_slug}"

        final_reply = (
            f"Successfully authored and published '{form_name}' (ID: {created_form_id}). "
            f"Configured with {len(synthesized_form.get('blocks', []))} jurisdiction blocks. "
            f"View live on UI at: {ui_link}"
        )

        if session_id:
            self.chat_listener.reply_to_session(session_id, final_reply, tool_name="Form.update")

        return {
            "success": all_success,
            "is_refusal": False,
            "prompt": prompt,
            "form_id": created_form_id,
            "form_name": form_name,
            "form_slug": form_slug,
            "ui_link": ui_link,
            "reply": final_reply,
            "event_log": event_log,
            "nodes": [{"id": n.node_id, "tool": n.tool_name, "state": n.state, "result": n.result, "error": n.error} for n in plan.nodes],
        }

    def process_latest_ui_chat_question(self) -> Optional[Dict[str, Any]]:
        persona_id = self.chat_listener.resolve_forms_persona_id()
        chat_data = self.chat_listener.poll_latest_question(persona_id)
        if not chat_data or not chat_data.get("question"):
            return None
        exec_res = self.execute_prompt(chat_data["question"], session_id=chat_data["session_id"])
        exec_res["chat_session_id"] = chat_data["session_id"]
        exec_res["chat_message_id"] = chat_data.get("message_id")
        return exec_res
