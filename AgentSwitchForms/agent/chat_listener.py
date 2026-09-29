"""
UI Chatbot Listener for AgentSwitch Forms Agent (Seat 25).
Retrieves questions asked to the Forms agent via the AgentSwitch UI chat bot (AgentSession and AgentMessage),
and posts assistant responses back to the conversation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from testing.client import FormsTestClient


class UIChatListener:
    """Interacts with AgentSwitch UI Chatbot via AgentSession and AgentMessage MCP tools."""

    def __init__(self, client: Optional[FormsTestClient] = None):
        self.client = client or FormsTestClient()

    def resolve_forms_persona_id(self) -> Optional[str]:
        """Resolves the Forms Agent persona from AgentPersona.list."""
        resp = self.client.call_tool("AgentPersona.list", {"search": "Forms", "limit": 10})
        if not resp.get("is_error"):
            data = resp.get("result", {}).get("data", [])
            if data:
                return data[0].get("id")
        return None

    def poll_latest_question(self, persona_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest natural language question posted by a user in the UI chatbot.
        Queries AgentSession.list -> AgentMessage.list.
        """
        args: Dict[str, Any] = {
            "channel": "web",
            "status": "active",
            "sort_by": "last_message_at",
            "sort_order": "desc",
            "limit": 1,
        }
        if persona_id:
            args["persona_id"] = persona_id

        # 1. Fetch active web chat session
        sess_resp = self.client.call_tool("AgentSession.list", args)
        if sess_resp.get("is_error"):
            return None

        sessions = sess_resp.get("result", {}).get("data", [])
        if not sessions:
            return None

        session = sessions[0]
        session_id = session.get("id")

        # 2. Fetch latest user message from the session
        msg_resp = self.client.call_tool(
            "AgentMessage.list",
            {"session_id": session_id, "role": "user", "sort_by": "created_at", "sort_order": "desc", "limit": 1},
        )
        if msg_resp.get("is_error"):
            return None

        messages = msg_resp.get("result", {}).get("data", [])
        if not messages:
            return None

        latest_msg = messages[0]
        return {
            "session_id": session_id,
            "session_title": session.get("title", ""),
            "message_id": latest_msg.get("id"),
            "question": latest_msg.get("content", ""),
            "role": latest_msg.get("role"),
            "raw_message": latest_msg,
        }

    def get_chat_message(self, message_id: str) -> Dict[str, Any]:
        """
        Retrieves a single AgentMessage record by ID via MCP get tool (AgentMessage.get).
        Returns the tool response envelope.
        """
        return self.client.call_tool("AgentMessage.get", {"id": message_id})

    def get_chat_message_via_rest(self, message_id: str) -> Dict[str, Any]:
        """
        Retrieves a single AgentMessage record by ID via REST HTTP GET (GET /api/AgentMessage/{id}).
        Returns the API response envelope.
        """
        return self.client.api_get(f"/api/AgentMessage/{message_id}")

    def reply_to_session(
        self,
        session_id: str,
        reply_text: str,
        tool_name: Optional[str] = None,
        tool_status: str = "ok",
    ) -> Dict[str, Any]:
        """
        Posts assistant reply back to the UI chat session.
        Uses AgentSession.update and updates activity state.
        """
        sess_update = self.client.call_tool(
            "AgentSession.update",
            {
                "id": session_id,
                "status": "active",
                "metadata": f'{{"last_reply_preview": "{reply_text[:120]}", "tool": "{tool_name or ""}"}}',
            },
        )
        return {
            "session_id": session_id,
            "reply_text": reply_text,
            "session_updated": not sess_update.get("is_error"),
        }
