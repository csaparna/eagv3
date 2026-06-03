"""
Decision — pick the next action for one bounded goal.

Returns either a final answer in plain text, or a single tool call to MCP.
Called once per iteration when there is an unfinished goal.
One LLM call routed via ``auto_route="decision"``.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from schemas import DecisionOutput, Goal, MemoryItem, ToolCall

sys.path.insert(0, str(Path(__file__).resolve().parent / "llm_gatewayV3"))
from client import LLM  # noqa: E402

# ── System prompt for the Decision LLM call ────────────────────────────────

_SYSTEM = """\
You are the Decision layer of an agentic loop.

You are given:
  - A single GOAL to work on (a short imperative statement).
  - MEMORY HITS: relevant items from the agent's memory.
  - ATTACHED ARTIFACTS: binary/text data fetched in a prior step (if any).
  - HISTORY: recent events from this run.
  - MCP TOOLS: the tool definitions available to you.

Your job:
  1. If you can fully answer the goal from the information at hand,
     reply in plain text with the answer.  Do NOT call a tool.
  2. If you need more information or need to perform an action, call
     exactly ONE tool from the MCP TOOLS list.  Pick the most useful
     tool and supply correct arguments.

NEVER fabricate tool names.  Only use tools from MCP TOOLS.
NEVER call a tool if you already have the answer.
Keep text answers concise.
"""


class Decision:
    """Pick the next action for a single bounded goal."""

    def next_step(
        self,
        goal: Goal,
        hits: list[MemoryItem],
        attached: list[tuple[str, bytes]],
        history: list[dict],
        mcp_tools: list[dict],
    ) -> DecisionOutput:
        """Decide the next step for *goal*.

        Parameters
        ----------
        goal : Goal
            The current unfinished goal to work on.
        hits : list[MemoryItem]
            Relevant memory items for context.
        attached : list[tuple[str, bytes]]
            Pairs of (artifact_id, raw_bytes) attached to this goal.
        history : list[dict]
            The run history so far.
        mcp_tools : list[dict]
            Tool definitions from the MCP server (gateway-compatible dicts).

        Returns
        -------
        DecisionOutput
            Either ``answer`` is set (goal can be answered) or ``tool_call``
            is set (one MCP tool to invoke next).
        """
        # ── Build the user-turn prompt ──────────────────────────────────
        parts: list[str] = [f"GOAL:\n{goal.text}\n"]

        # Memory hits
        if hits:
            hits_text = "\n".join(
                f"- [{h.kind}] {h.descriptor}: {json.dumps(h.value, default=str)}"
                for h in hits[:10]
            )
            parts.append(f"MEMORY HITS:\n{hits_text}\n")

        # Attached artifacts
        if attached:
            for aid, blob in attached:
                try:
                    text = blob.decode("utf-8")
                    if len(text) > 2000:
                        text = text[:2000] + f"\n... ({len(blob)} bytes total)"
                    parts.append(f"ATTACHED ARTIFACT ({aid}):\n{text}\n")
                except UnicodeDecodeError:
                    b64 = base64.b64encode(blob[:2000]).decode("ascii")
                    parts.append(
                        f"ATTACHED ARTIFACT ({aid}, binary, {len(blob)} bytes):\n"
                        f"base64 preview: {b64}\n"
                    )

        # Recent history (last 15 events)
        recent = history[-15:] if len(history) > 15 else history
        if recent:
            history_text = json.dumps(recent, indent=2, default=str)
            parts.append(f"HISTORY (last {len(recent)} events):\n{history_text}\n")

        prompt = "\n".join(parts)

        # ── LLM call with native tool-use ───────────────────────────────
        llm = LLM()
        reply = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=_SYSTEM,
            auto_route="decision",
            tools=mcp_tools if mcp_tools else None,
            tool_choice="auto" if mcp_tools else None,
            temperature=0,
            max_tokens=2048,
        )

        # ── Parse: tool_call or answer ──────────────────────────────────
        tool_calls = reply.get("tool_calls") or []
        if tool_calls:
            tc = tool_calls[0]  # Take the first tool call only.
            return DecisionOutput(
                answer=None,
                tool_call=ToolCall(
                    name=tc["name"],
                    arguments=tc.get("arguments", {}),
                ),
            )

        # No tool call — the LLM answered directly.
        text = reply.get("text", "").strip()
        return DecisionOutput(answer=text or "(no answer)", tool_call=None)
