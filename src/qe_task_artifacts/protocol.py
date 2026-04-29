from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class ArtifactWriter(Protocol):
    """Protocol for task-scoped artifact saving.

    Implementations decide where artifacts are stored. Physics code should only
    depend on this interface and should not know task IDs, auth tokens, or S3
    details.
    """

    def save(
        self,
        name: str,
        obj: Any,
        *,
        format: Optional[str] = None,
    ) -> Any:
        """Serialize and save an object under a task-relative artifact name."""
        ...

    def write_text(self, name: str, text: str) -> Any:
        """Save text under a task-relative artifact name."""
        ...

    def write_bytes(self, name: str, data: bytes) -> Any:
        """Save bytes under a task-relative artifact name."""
        ...

    def enabled(self) -> bool:
        """Return whether artifact saving is available for this execution."""
        ...
