"""
Memory — typed store for facts, preferences, tool outcomes, and scratchpad entries.

The agent6 loop loads on first read and writes back after every mutation.
Across runs the same JSON file (``state/memory.json``) is reused, so
preferences and facts persist.  Clearing the file resets the agent.

Read methods (``read``, ``filter``) use no LLM — just keyword overlap and
structured filtering.  ``relevant`` uses one LLM call routed via
``auto_route="memory"`` for semantic scoring when keyword recall is weak.

Write methods:
    ``remember``        — LLM classifies ambiguous free-form text (one call).
    ``record_outcome``  — deterministic construction, no LLM.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from schemas import MemoryItem

# Gateway client lives one directory up inside llm_gatewayV3/
sys.path.insert(0, str(Path(__file__).resolve().parent / "llm_gatewayV3"))
from client import LLM  # noqa: E402

_STATE_PATH = Path(__file__).resolve().parent / "state" / "memory.json"

# ── tokeniser helper ────────────────────────────────────────────────────────

_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def _tokens(text: str) -> set[str]:
    """Lowercase alphanumeric tokens from *text*."""
    return {t for t in _SPLIT_RE.split(text.lower()) if len(t) >= 2}


# ── LLM classification schema for ``remember`` ─────────────────────────────

class _ClassifyResult(BaseModel):
    kind: str        # one of fact | preference | scratchpad
    keywords: list[str]
    descriptor: str  # one short human-readable line
    value: dict      # structured payload
    confidence: float


# ── Memory class ────────────────────────────────────────────────────────────

class Memory:
    """In-memory item list backed by a JSON file on disk."""

    def __init__(self, state_path: Path = _STATE_PATH) -> None:
        self._path = state_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)

        self._items: list[MemoryItem] = []
        self._loaded = False

    # ── persistence ──────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Lazy-load from disk on first access."""
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            return
        try:
            text = self._path.read_text(encoding="utf-8").strip()
            if not text:
                return
            raw = json.loads(text)
            self._items = [MemoryItem.model_validate(r) for r in raw]
        except (json.JSONDecodeError, OSError, ValueError):
            # Corrupted file — start fresh.
            self._items = []

    def _save(self) -> None:
        """Flush the full item list to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = [item.model_dump(mode="json") for item in self._items]
        self._path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # ── scoring ──────────────────────────────────────────────────────────

    @staticmethod
    def _score(query: str, item: MemoryItem) -> float:
        """Keyword-overlap score between *query* and *item*.

        Tokenises both the query and the item's keywords + descriptor,
        then returns a Jaccard-like ratio.
        """
        q_tokens = _tokens(query)
        if not q_tokens:
            return 0.0
        item_tokens = set(kw.lower() for kw in item.keywords) | _tokens(item.descriptor)
        if not item_tokens:
            return 0.0
        overlap = q_tokens & item_tokens
        return len(overlap) / len(q_tokens | item_tokens)

    # ── read methods (no LLM) ────────────────────────────────────────────

    def read(
        self,
        query: str,
        history: list[dict],
        kinds: list[str] | None = None,
        top_k: int = 8,
    ) -> list[MemoryItem]:
        """Keyword-overlap search.  Returns ranked top-k items."""
        self._ensure_loaded()
        pool = self._items
        if kinds:
            pool = [it for it in pool if it.kind in kinds]

        scored = [(self._score(query, it), it) for it in pool]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [it for _, it in scored[:top_k]]

    def filter(
        self,
        kinds: list[str],
        goal_id: str | None = None,
        recent: int | None = None,
    ) -> list[MemoryItem]:
        """Structured filter by kind, goal_id, recency (last *recent* items)."""
        self._ensure_loaded()
        pool = [it for it in self._items if it.kind in kinds]
        if goal_id is not None:
            pool = [it for it in pool if it.goal_id == goal_id]
        if recent is not None:
            pool = pool[-recent:]
        return pool

    # ── read method (LLM scored) ─────────────────────────────────────────

    def relevant(
        self,
        query: str,
        kinds: list[str] | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """LLM-scored relevance over a kind-filtered candidate pool.

        Used only when keyword recall is weak.  One gateway call routed
        via ``auto_route="memory"``.
        """
        self._ensure_loaded()
        pool = self._items
        if kinds:
            pool = [it for it in pool if it.kind in kinds]
        if not pool:
            return []

        # Build candidate summaries for the LLM to rank.
        candidates = "\n".join(
            f"[{i}] ({it.kind}) {it.descriptor}"
            for i, it in enumerate(pool)
        )

        llm = LLM()
        reply = llm.chat(
            prompt=(
                f"Given the query: {query!r}\n\n"
                f"Rank the following memory items by relevance to the query.  "
                f"Return ONLY a JSON array of the integer indices, most relevant first.  "
                f"Return at most {top_k} indices.\n\n{candidates}"
            ),
            system="You are a relevance ranker.  Return only a JSON array of integers.",
            auto_route="memory",
            temperature=0,
            max_tokens=256,
        )

        # Parse the ranked indices from the LLM response.
        try:
            text = reply.get("text", "").strip()
            # Handle possible markdown code fences.
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            indices = json.loads(text)
            if not isinstance(indices, list):
                indices = []
        except (json.JSONDecodeError, TypeError):
            indices = []

        result: list[MemoryItem] = []
        seen: set[int] = set()
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(pool) and idx not in seen:
                result.append(pool[idx])
                seen.add(idx)
            if len(result) >= top_k:
                break
        return result

    # ── write methods ────────────────────────────────────────────────────

    def remember(
        self,
        raw_text: str,
        source: str,
        run_id: str,
        goal_id: str,
    ) -> MemoryItem:
        """Classify ambiguous free-form content into a typed MemoryItem.

        One LLM call (``auto_route="memory"``, pinned to Gemini) extracts
        kind, keywords, descriptor, value, and confidence.
        """
        self._ensure_loaded()

        schema = _ClassifyResult.model_json_schema()
        llm = LLM()
        reply = llm.chat(
            prompt=(
                f"Classify this content into a memory item.\n\n"
                f"Content: {raw_text!r}\n"
                f"Source: {source!r}\n\n"
                f"Rules:\n"
                f"- kind must be one of: fact, preference, scratchpad\n"
                f"- keywords: 3-8 lowercase terms useful for search\n"
                f"- descriptor: one short human-readable summary line\n"
                f"- value: a structured dict capturing the key information\n"
                f"- confidence: 0.0 to 1.0, how certain you are about the classification\n"
            ),
            system="You are a memory classifier. Return a single JSON object matching the schema.",
            auto_route="memory",
            response_format={
                "type": "json_schema",
                "schema": schema,
                "name": "ClassifyResult",
                "strict": True,
            },
            temperature=0,
            max_tokens=512,
        )

        # Parse the classified result.
        if reply.get("parsed"):
            classified = _ClassifyResult.model_validate(reply["parsed"])
        else:
            # Fallback: try parsing the text as JSON.
            try:
                text = reply.get("text", "").strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                classified = _ClassifyResult.model_validate_json(text)
            except Exception:
                # Last resort: minimal classification.
                classified = _ClassifyResult(
                    kind="scratchpad",
                    keywords=list(_tokens(raw_text))[:5],
                    descriptor=raw_text[:120],
                    value={"raw": raw_text},
                    confidence=0.3,
                )

        # Validate kind is one of the allowed values.
        valid_kinds = {"fact", "preference", "scratchpad"}
        kind = classified.kind if classified.kind in valid_kinds else "scratchpad"

        item = MemoryItem(
            id=f"mem:{uuid.uuid4().hex[:12]}",
            kind=kind,
            keywords=classified.keywords,
            descriptor=classified.descriptor,
            value=classified.value,
            artifact_id=None,
            source=source,
            run_id=run_id,
            goal_id=goal_id,
            confidence=classified.confidence,
            created_at=datetime.now(timezone.utc),
        )

        self._items.append(item)
        self._save()
        return item

    def record_outcome(
        self,
        tool_call: dict,
        result_text: str,
        artifact_id: str | None = None,
        success: bool | None = None,
    ) -> MemoryItem:
        """Record an MCP tool-call outcome.  No LLM call.

        Kind is ``tool_outcome`` by construction; keywords come from the
        tool name and argument tokens.
        """
        self._ensure_loaded()

        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("arguments", {})

        # Build keywords from the tool name and argument values.
        kw_set = _tokens(tool_name)
        for v in tool_args.values():
            kw_set |= _tokens(str(v))
        keywords = sorted(kw_set)[:10]

        # Build a short descriptor.
        args_summary = ", ".join(f"{k}={v!r}" for k, v in list(tool_args.items())[:3])
        descriptor = f"{tool_name}({args_summary})"
        if len(descriptor) > 120:
            descriptor = descriptor[:117] + "..."

        item = MemoryItem(
            id=f"mem:{uuid.uuid4().hex[:12]}",
            kind="tool_outcome",
            keywords=keywords,
            descriptor=descriptor,
            value={
                "tool": tool_name,
                "arguments": tool_args,
                "result_preview": result_text[:500],
                "success": success,
            },
            artifact_id=artifact_id,
            source=f"tool:{tool_name}",
            run_id="",     # caller should set via agent loop context
            goal_id=None,  # caller should set via agent loop context
            confidence=1.0,
            created_at=datetime.now(timezone.utc),
        )

        self._items.append(item)
        self._save()
        return item
