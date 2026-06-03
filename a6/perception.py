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
You are the Perception layer of an agentic loop.  You manage a goal list.

RULES (follow exactly):
1. If PRIOR GOALS is empty, decompose the USER QUERY into one or more bounded
   goals.  Each goal is a short imperative statement.  Assign each a unique id
   like "g1", "g2", etc.  Set done=false and attach_artifact_id=null.

2. For each prior goal, examine the HISTORY.  Mark done=true the moment the
   history contains a tool outcome that satisfies the goal.  Once a goal is
   done it stays done forever.

3. For the FIRST unfinished goal, check whether it needs raw bytes from a
   previously fetched artifact.  If so, set attach_artifact_id to the
   artifact handle (e.g. "art:abcdef0123456789") from MEMORY HITS.

4. NEVER reorder, insert in the middle, or drop goals.  Only append new goals
   at the end if needed.

Return a JSON object matching the Observation schema: {"goals": [...]}.
Each goal: {"id": str, "text": str, "done": bool, "attach_artifact_id": str|null}.
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
