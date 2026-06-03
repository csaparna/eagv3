"""
Action — dispatch the chosen MCP tool.

Pushes large results to the artifact store and returns a short descriptor.
Called only when Decision returns a tool_call.
No LLM call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from artifacts import ArtifactStore
from schemas import ToolCall

if TYPE_CHECKING:
    from mcp import ClientSession

# Results larger than this threshold are stored in the artifact store
# and only a short descriptor is returned to the agent loop.
_OVERFLOW_BYTES = 4096


class Action:
    """Execute a single MCP tool call."""

    def __init__(self, artifact_store: ArtifactStore | None = None) -> None:
        self._store = artifact_store or ArtifactStore()

    async def execute(
        self,
        session: ClientSession,
        tool_call: ToolCall,
    ) -> tuple[str, str | None]:
        """Dispatch *tool_call* via MCP and return ``(descriptor, artifact_id)``.

        Parameters
        ----------
        session : ClientSession
            An initialised MCP client session.
        tool_call : ToolCall
            The tool name and arguments to invoke.

        Returns
        -------
        tuple[str, str | None]
            A short text descriptor of the result, and an optional artifact
            handle if the result was large enough to overflow into the store.
        """
        # ── Dispatch via MCP ────────────────────────────────────────────
        result = await session.call_tool(tool_call.name, tool_call.arguments)

        # Extract text from the MCP result content blocks.
        text_parts: list[str] = []
        for block in result.content or []:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        result_text = "\n".join(text_parts) if text_parts else ""

        # ── Small result: return inline ─────────────────────────────────
        if len(result_text.encode("utf-8")) < _OVERFLOW_BYTES:
            return result_text, None

        # ── Large result: overflow to artifact store ────────────────────
        blob = result_text.encode("utf-8")
        descriptor = (
            f"{tool_call.name} result ({len(blob)} bytes): "
            f"{result_text[:200]}..."
        )
        artifact_id = self._store.put(
            blob,
            content_type="text/plain",
            source=f"tool:{tool_call.name}",
            descriptor=descriptor[:120],
        )
        short_desc = (
            f"[stored as {artifact_id}] "
            f"{tool_call.name}: {result_text[:200]}..."
        )
        return short_desc, artifact_id
