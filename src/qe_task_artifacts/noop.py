from __future__ import annotations

from typing import Any, Optional


class NoopArtifactWriter:
    """Artifact writer that accepts calls and intentionally does nothing."""

    def save(
        self,
        name: str,
        obj: Any,
        *,
        format: Optional[str] = None,
    ) -> None:
        return None

    def write_text(self, name: str, text: str) -> None:
        return None

    def write_bytes(self, name: str, data: bytes) -> None:
        return None

    def enabled(self) -> bool:
        return False
