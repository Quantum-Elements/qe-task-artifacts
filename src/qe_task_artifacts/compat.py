from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from .protocol import ArtifactWriter

F = TypeVar("F", bound=Callable[..., Any])


def supports_artifacts(fn: Callable[..., Any]) -> bool:
    """Return whether ``fn`` can accept an ``artifacts=`` keyword."""
    if getattr(fn, "_accepts_artifacts", False):
        return True

    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return False

    if "artifacts" in signature.parameters:
        return True

    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def call_with_optional_artifacts(
    fn: Callable[..., Any],
    *args: Any,
    artifacts: Optional[ArtifactWriter] = None,
    **kwargs: Any,
) -> Any:
    """Call ``fn`` with artifacts only when its signature supports it."""
    if artifacts is not None and supports_artifacts(fn):
        kwargs["artifacts"] = artifacts
    return fn(*args, **kwargs)


def accepts_artifacts(fn: F) -> F:
    """Decorate an old function so it accepts and ignores ``artifacts=``.

    This is a migration helper for physics functions that do not yet use
    artifact saving. Once a function genuinely uses artifacts, add an explicit
    ``artifacts=None`` parameter instead.
    """
    if supports_artifacts(fn):
        return fn

    @wraps(fn)
    def wrapper(*args: Any, artifacts: Optional[ArtifactWriter] = None, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    wrapper._accepts_artifacts = True  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]
