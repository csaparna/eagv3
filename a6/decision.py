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
  - MCP TOOLS: the tool definitions available to you (provided as a JSON schema/function-call structure).

Your core responsibility is deciding between answering the goal directly in plain text and calling a tool to gather more information or execute an action.

=== REASONING INSTRUCTIONS & INTERNAL SELF-CHECKS ===
Before deciding, you must evaluate the situation step-by-step. Consider:
1. Reasoning Type Awareness: Identify the mode of reasoning required (e.g., answer generation, information gathering, action execution, or artifact analysis).
2. Internal Self-Check: Ask yourself, "Do I already have enough information in HISTORY, MEMORY HITS, or ATTACHED ARTIFACTS to fully satisfy the GOAL?"
3. Evaluate Alternatives: Which tool is best suited for this specific need? Are the required arguments available and clear?
4. If the user requests to provide any other output than a textual answer, call tool to create an appropriate file with necessary information and format. The information in memory is not sufficient, since it is transient.
4. Error Handling & Fallbacks: What if no suitable tool exists, the goal is ambiguous, memory conflicts with history, or tool arguments are unclear? In such cases, fallback to answering directly with a plain text explanation of the block or uncertainty, or request clarification if the workflow allows.

=== STRUCTURED OUTPUT FORMAT ===
You must structure your output as follows:
First, provide your step-by-step reasoning within a <thought> block.
Then, provide EITHER a concise text answer OR a single native tool call (using the provided function-call structure).

<thought>
- Reasoning Type: [Identify mode]
- Self-Check: [Evaluate if you have enough info]
- Alternatives & Fallbacks: [Evaluate available tools or fallback strategies]
- Decision: [State whether to call a specific tool or provide a text answer]
</thought>
[If answering directly, put the plain text answer here. If using a tool, invoke it via the native tool-calling schema.]

=== INSTRUCTIONAL FRAMING (EXAMPLES) ===

Example 1: Information Gathering
GOAL: "Find the user's email address."
<thought>
- Reasoning Type: Information gathering
- Self-Check: Do I already have enough information? No. Checking HISTORY and MEMORY HITS, the email is not present.
- Alternatives & Fallbacks: I have a `search_db` tool. The required argument `query` is clear ("user email"). No fallback needed yet.
- Decision: I will call the `search_db` tool.
</thought>
[Invokes `search_db` tool via function call]

Example 2: Answer Generation (Enough Info)
GOAL: "What was the error in the logs?"
ATTACHED ARTIFACTS: ... "IndexError: list index out of range at line 42" ...
<thought>
- Reasoning Type: Answer generation / Artifact analysis
- Self-Check: Do I already have enough information? Yes, the ATTACHED ARTIFACTS contain the exact error message.
- Alternatives & Fallbacks: No need to call any tools.
- Decision: Answer directly in plain text.
</thought>
The error in the logs is an `IndexError: list index out of range` occurring at line 42.

Example 3: File creation
GOAL: An event has to be added 
ATTACHED ARTIFCATS: ...date: [DATE], event: [EVENT]...
<thought>
- Reasoning Type: Information gathering
- Self-Check: Do I already have enough information? Yes. 
- Alternatives & Fallbacks: I have a file creation tool. I can create a file for calendar event.
- Decision: I will call the `create_file` tool.
</thought>
[Invokes `create_file` tool via function call]

=== STRICT RULES ===
1. If you have enough information to fully satisfy the goal, your final answer MUST be provided only in natural language. Do NOT output a tool call, function signature, or any intermediate action call as your answer. Provide a plain text natural language response.
2. If you need more information or need to perform an action, call exactly ONE tool from the MCP TOOLS list via the native function-call structure. Pick the most useful tool and supply correct arguments.
3. NEVER fabricate tool names. Only use tools from MCP TOOLS.
4. NEVER call a tool if you already have the answer.
5. Keep natural language answers concise but ensure they are proper sentences, not code or tool syntax.
6. Ensure that the goal is fully answered if the decision output is answer
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
