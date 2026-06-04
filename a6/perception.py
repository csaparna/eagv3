"""
Perception — observe the current state and manage the goal list.

One LLM call per invocation (``auto_route="perception"``).

The contract that Perception fulfills is four obligations:

1. If the prior goal list is empty, decompose the query into one or more
   bounded goals, each a short imperative statement.

2. For each prior goal, examine the run history. Mark the goal ``done: true``
   the moment the history contains an action that satisfies it. Once done,
   the goal remains done in every subsequent iteration.

3. For the first unfinished goal in the list, decide whether it needs raw
   bytes from a previously fetched artifact. If yes, set the goal's
   ``attach_artifact_id`` to one of the artifact handles in MEMORY HITS.

4. Preserve goal order. Do not reorder, do not insert in the middle,
   do not drop a goal.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from schemas import Goal, MemoryItem, Observation

sys.path.insert(0, str(Path(__file__).resolve().parent / "llm_gatewayV3"))
from client import LLM  # noqa: E402

# ── System prompt for the Perception LLM call ──────────────────────────────

_SYSTEM = """\
You are the Perception layer of an agentic loop. You manage the agent's goal list by observing the current state and making deterministic decisions.

Return a JSON object matching the Observation schema: {"goals": [...]}.
Each goal format: {"id": str, "text": str, "done": bool, "attach_artifact_id": str|null}.

REASONING PROCESS (Follow this mentally before generating output):
1. Reasoning Type Awareness: Identify your active reasoning mode:
   - Decomposition: If PRIOR GOALS is empty, your task is to break down the USER QUERY.
   - History Inspection: If PRIOR GOALS exists, evaluate HISTORY for goal completion.
   - Artifact Lookup: Check if the FIRST unfinished goal requires an artifact from MEMORY HITS.

2. Internal Self-Checks & Execution:
   - Decomposing Goals: Break the USER QUERY into short, bounded imperative statements. Order the goals sensibly if there are dependencies between them. Assign IDs ("g1", "g2", etc.). Set `done=false` and `attach_artifact_id=null`.
   - Evaluating Completion: Examine HISTORY. Mark `done=true` ONLY when the goal's answer is explicitly available as natural language in the HISTORY. Merely calling a tool or getting raw tool output is NOT enough to mark a goal done. You must wait for the final natural language answer. Once done, it stays done.
     * Self-Check: Validate goal completion. Is the explicit natural language answer present in the HISTORY?
   - Attaching Artifacts: For the FIRST unfinished goal ONLY, check if it needs raw bytes from a previously fetched artifact.
     * Self-Check: Validate artifact references. Ensure the artifact ID exactly matches an entry in MEMORY HITS.
   - Contradictions Check: Ensure the current state does not contradict past successes.
   - Order Preservation: NEVER reorder, insert in the middle, or drop goals. Only append new goals if new requirements arise.

ERROR HANDLING & FALLBACKS:
- Ambiguous History / Uncertain Satisfaction: If it's unclear whether an action satisfied a goal, or if only raw tool output is present without a natural language answer, keep `done=false`.
- Missing / Invalid Artifacts: If a goal needs an artifact but it's not in MEMORY HITS, or the ID is invalid, set `attach_artifact_id=null`.

EXAMPLES:

Example 1: Goal Decomposition
Input:
PRIOR GOALS: (none)
USER QUERY: "Fetch the config and extract the database URL."
Output:
{
  "goals": [
    {"id": "g1", "text": "Fetch the config file.", "done": false, "attach_artifact_id": null},
    {"id": "g2", "text": "Extract the database URL from the config.", "done": false, "attach_artifact_id": null}
  ]
}

Example 2: History Inspection (Edge Case: Uncertain satisfaction)
Input:
PRIOR GOALS: [{"id": "g1", "text": "Fetch config.", "done": false, "attach_artifact_id": null}]
HISTORY: [{"action": "list_dir", "status": "success", "files": ["config.json"]}]
MEMORY HITS: (none)
Output:
{
  "goals": [
    {"id": "g1", "text": "Fetch config.", "done": false, "attach_artifact_id": null}
  ]
}

Example 3: Successful Completion and Artifact Attachment
Input:
PRIOR GOALS: [
  {"id": "g1", "text": "Fetch config.", "done": false, "attach_artifact_id": null},
  {"id": "g2", "text": "Extract DB URL.", "done": false, "attach_artifact_id": null}
]
HISTORY: [{"action": "read_file", "file": "config.json", "status": "success"}]
MEMORY HITS: - [tool_outcome] Fetched config.json  artifact_id=art:123
Output:
{
  "goals": [
    {"id": "g1", "text": "Fetch config.", "done": true, "attach_artifact_id": null},
    {"id": "g2", "text": "Extract DB URL.", "done": false, "attach_artifact_id": "art:123"}
  ]
}
"""


class Perception:
    """Observe the agent's state and produce an updated goal list."""

    def observe(
        self,
        query: str,
        hits: list[MemoryItem],
        history: list[dict],
        prior_goals: list[Goal],
        run_id: str,
    ) -> Observation:
        """Run one perception cycle.

        Parameters
        ----------
        query : str
            The original user query.
        hits : list[MemoryItem]
            Memory items retrieved for this iteration.
        history : list[dict]
            The full run history so far (list of event dicts).
        prior_goals : list[Goal]
            The goal list from the previous iteration (may be empty on turn 1).
        run_id : str
            Current run identifier.

        Returns
        -------
        Observation
            Updated goal list.
        """
        # ── Build the user-turn prompt ──────────────────────────────────
        parts: list[str] = [f"USER QUERY:\n{query}\n"]

        # Prior goals
        if prior_goals:
            goals_text = json.dumps(
                [g.model_dump(mode="json") for g in prior_goals], indent=2
            )
            parts.append(f"PRIOR GOALS:\n{goals_text}\n")
        else:
            parts.append("PRIOR GOALS: (none — this is the first iteration)\n")

        # Memory hits
        if hits:
            hits_text = "\n".join(
                f"- [{h.kind}] {h.descriptor}"
                + (f"  artifact_id={h.artifact_id}" if h.artifact_id else "")
                for h in hits
            )
            parts.append(f"MEMORY HITS:\n{hits_text}\n")
        else:
            parts.append("MEMORY HITS: (none)\n")

        # Recent history (last 20 events to keep prompt bounded)
        recent = history[-20:] if len(history) > 20 else history
        if recent:
            history_text = json.dumps(recent, indent=2, default=str)
            parts.append(f"HISTORY (last {len(recent)} events):\n{history_text}\n")
        else:
            parts.append("HISTORY: (none)\n")

        prompt = "\n".join(parts)

        # ── Structured-output call ──────────────────────────────────────
        schema = Observation.model_json_schema()
        llm = LLM()
        reply = llm.chat(
            prompt=prompt,
            system=_SYSTEM,
            auto_route="perception",
            response_format={
                "type": "json_schema",
                "schema": schema,
                "name": "Observation",
                "strict": True,
            },
            temperature=0,
            max_tokens=1024,
        )

        # ── Parse response ──────────────────────────────────────────────
        if reply.get("parsed"):
            return Observation.model_validate(reply["parsed"])

        # Fallback: try parsing text as JSON.
        text = reply.get("text", "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return Observation.model_validate_json(text)
        except Exception:
            pass

        # Last resort: if we had prior goals, return them unchanged.
        if prior_goals:
            return Observation(goals=prior_goals)

        # Absolute fallback: single goal from the raw query.
        return Observation(
            goals=[
                Goal(id="g1", text=query, done=False, attach_artifact_id=None)
            ]
        )
