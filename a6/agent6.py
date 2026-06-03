"""
agent6.py — Goal-directed agentic loop.

Perceive → Decide → Act cycle over MCP tools, with durable memory
and artifact storage.  The LLM Gateway V3 routes each cognitive layer
(perception / memory / decision) to an appropriate model tier.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from schemas import MemoryItem, Artifact, Observation, Goal, DecisionOutput
from memory import Memory
from artifacts import ArtifactStore
from perception import Perception
from decision import Decision
from action import Action

MAX_ITERATIONS = 15

# ── Module-level singletons ─────────────────────────────────────────────────

memory = Memory()
store = ArtifactStore()
perception = Perception()
decide = Decision()
act = Action(artifact_store=store)

# ── Helpers ─────────────────────────────────────────────────────────────────


def ensure_gateway() -> None:
    """Verify LLM Gateway V3 is reachable, or raise early."""
    url = os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")
    try:
        r = httpx.get(f"{url}/v1/capabilities", timeout=5)
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(
            f"LLM Gateway V3 not reachable at {url}. "
            f"Start it with:  cd llm_gatewayV3 && bash run.sh\n{e}"
        ) from e


@asynccontextmanager
async def mcp_session():
    """Spawn mcp_server.py as a subprocess and yield an initialised session."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("mcp_server.py"))],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def load_tools(session: ClientSession) -> list:
    """Return the raw MCP tool objects from the server."""
    return (await session.list_tools()).tools


def mcp_tools_for_decision(mcp_tools) -> list[dict]:
    """Reshape MCP tool definitions into the gateway's ToolDef format."""
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema or {"type": "object", "properties": {}},
        }
        for t in mcp_tools
    ]


# ── Agent loop ──────────────────────────────────────────────────────────────


async def run(query: str) -> str:
    ensure_gateway()
    run_id = uuid.uuid4().hex[:8]
    history: list[dict] = []
    prior_goals: list[Goal] = []

    # Durable memory: classify the user's query so facts/preferences
    # in it survive into future runs.
    memory.remember(query, source="user_query", run_id=run_id, goal_id="")

    async with mcp_session() as session:
        mcp_tools = await load_tools(session)
        tools = mcp_tools_for_decision(mcp_tools)

        for it in range(1, MAX_ITERATIONS + 1):
            print(f"\n[Iteration {it}] ── memory.read ──")
            hits = memory.read(query, history)
            print(f"  -> Found {len(hits)} memory hits")

            print(f"[Iteration {it}] ── perception.observe ──")
            obs = perception.observe(query, hits, history, prior_goals, run_id)
            prior_goals = obs.goals
            print(f"  -> {len(obs.goals)} goals, {sum(1 for g in obs.goals if g.done)} done")

            if all(g.done for g in obs.goals):
                print("  -> All goals complete!")
                break

            # First unfinished goal
            goal = next((g for g in obs.goals if not g.done), None)
            if goal is None:
                break

            # Attach artifact bytes if the goal requests one
            attached: list[tuple[str, bytes]] = []
            if goal.attach_artifact_id and store.exists(goal.attach_artifact_id):
                attached.append(
                    (goal.attach_artifact_id,
                     store.get_bytes(goal.attach_artifact_id))
                )

            print(f"[Iteration {it}] ── decide.next_step ──")
            print(f"  -> Goal: {goal.text}")
            decision = decide.next_step(goal, hits, attached, history, tools)

            if decision.answer is not None:
                print(f"  -> Decision: Answered directly ({len(decision.answer)} chars)")
                history.append({
                    "kind": "answer",
                    "goal_id": goal.id,
                    "text": decision.answer,
                })
                goal.done = True
                continue

            # ── Act ──────────────────────────────────────────────
            print(f"[Iteration {it}] ── act.execute ──")
            print(f"  -> Tool: {decision.tool_call.name}({decision.tool_call.arguments})")
            descriptor, artifact_id = await act.execute(
                session, decision.tool_call
            )
            print(f"  -> Result: {descriptor}")
            history.append({
                "kind": "tool_call",
                "goal_id": goal.id,
                "tool": decision.tool_call.name,
                "arguments": decision.tool_call.arguments,
                "result": descriptor,
                "artifact_id": artifact_id,
            })
            memory.record_outcome(
                tool_call=decision.tool_call.model_dump(),
                result_text=descriptor,
                artifact_id=artifact_id,
            )

    # ── Synthesise final answer from the last few outcomes ───────────────
    outcomes = memory.filter(kinds=["tool_outcome"])
    answers = [
        ev["text"] for ev in history if ev.get("kind") == "answer"
    ]
    if answers:
        return "\n".join(answers)
    if outcomes:
        return "\n".join(it.descriptor for it in outcomes[-5:])
    return "(no result)"


# ── Entrypoint ──────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="agent6 — goal-directed agentic loop"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="What time is it in Denver?",
    )
    args = parser.parse_args()

    print("═" * 60)
    print(f"agent6  query: {args.query}")
    print("═" * 60)

    result = asyncio.run(run(args.query))

    print(f"\n{'═' * 60}")
    print(f"FINAL ANSWER:\n{result}")
    print("═" * 60)


if __name__ == "__main__":
    main()