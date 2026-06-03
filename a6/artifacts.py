"""
ArtifactStore — content-addressable blob storage for the agent loop.

Handles are short strings of the form ``art:<sha256-prefix>``.  Storage is
two files per artifact under ``state/artifacts/``:

    <prefix>.bin   — raw bytes
    <prefix>.json  — Artifact metadata

The store is content-addressable; identical fetches deduplicate automatically.
No LLM calls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from schemas import Artifact

_DEFAULT_DIR = Path(__file__).resolve().parent / "state" / "artifacts"


class ArtifactStore:
    """SHA-256-keyed blob store on local disk."""

    def __init__(self, root: Path = _DEFAULT_DIR) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _prefix(blob: bytes) -> str:
        """First 16 hex characters of the SHA-256 digest."""
        return hashlib.sha256(blob).hexdigest()[:16]

    @staticmethod
    def _id_to_prefix(artifact_id: str) -> str:
        """Strip the ``art:`` scheme prefix."""
        if artifact_id.startswith("art:"):
            return artifact_id[4:]
        return artifact_id

    def _bin_path(self, prefix: str) -> Path:
        return self._root / f"{prefix}.bin"

    def _meta_path(self, prefix: str) -> Path:
        return self._root / f"{prefix}.json"

    # ── public API ───────────────────────────────────────────────────────

    def put(
        self,
        blob: bytes,
        *,
        content_type: str,
        source: str,
        descriptor: str,
    ) -> str:
        """Store *blob* and return its artifact handle ``art:<prefix>``."""
        prefix = self._prefix(blob)
        aid = f"art:{prefix}"

        # Write blob (idempotent for identical content).
        self._bin_path(prefix).write_bytes(blob)

        # Write / overwrite metadata sidecar.
        meta = Artifact(
            id=aid,
            content_type=content_type,
            size_bytes=len(blob),
            source=source,
            descriptor=descriptor,
        )
        self._meta_path(prefix).write_text(
            json.dumps(meta.model_dump(), indent=2),
            encoding="utf-8",
        )
        return aid

    def get_bytes(self, artifact_id: str) -> bytes:
        """Return raw bytes for *artifact_id*."""
        prefix = self._id_to_prefix(artifact_id)
        path = self._bin_path(prefix)
        if not path.exists():
            raise FileNotFoundError(f"No blob for artifact {artifact_id!r}")
        return path.read_bytes()

    def get_meta(self, artifact_id: str) -> Artifact:
        """Return the ``Artifact`` metadata record."""
        prefix = self._id_to_prefix(artifact_id)
        path = self._meta_path(prefix)
        if not path.exists():
            raise FileNotFoundError(f"No metadata for artifact {artifact_id!r}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Artifact.model_validate(data)

    def exists(self, artifact_id: str) -> bool:
        """Check whether *artifact_id* has been stored."""
        prefix = self._id_to_prefix(artifact_id)
        return self._bin_path(prefix).exists()
