"""Context-injected artifact saving.

This module gives QEAM/physics code a "just decorate and save" experience:

    @with_artifacts
    def my_qeam_function(input_data, gate):
        result = compute(...)
        save_artifact("output/result.json", result, format="json")
        return result

The decorator accepts an optional ``artifacts=`` kwarg from the caller and
parks it in a ``ContextVar`` for the duration of the call. ``save_artifact``
(and ``write_text`` / ``write_bytes``) reads from that ``ContextVar`` and
forwards to the active writer.

When no writer is active (local runs, unit tests, REPL), every save call
becomes a safe no-op.

Worker integration: the concrete worker writer (e.g. ``TaskFileContext`` in
``julia-celery-worker``) can call :func:`set_current_artifacts` in its own
``__enter__`` to make ``save_artifact`` automatically target the running
task -- so QEAM functions can be decorated and use ``save_artifact`` without
the worker having to plumb ``artifacts=`` at the call site.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from .noop import NoopArtifactWriter
from .protocol import ArtifactWriter

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_WRITER: ArtifactWriter = NoopArtifactWriter()
_CURRENT: ContextVar[ArtifactWriter] = ContextVar(
    "qe_task_artifacts_current", default=_DEFAULT_WRITER
)


def current_artifacts() -> ArtifactWriter:
    """Return the active :class:`ArtifactWriter`.

    Falls back to a :class:`NoopArtifactWriter` (``enabled()`` is ``False``)
    when no writer has been set.
    """
    return _CURRENT.get()


def set_current_artifacts(writer: ArtifactWriter) -> Token:
    """Set the active writer and return a token usable with :func:`reset_current_artifacts`.

    Intended for the worker / concrete-writer side, so that ``save_artifact``
    inside QEAM picks up the running task's writer automatically. Most QEAM
    code should not call this directly; use :func:`with_artifacts` instead.
    """
    return _CURRENT.set(writer)


def reset_current_artifacts(token: Token) -> None:
    """Reset the active writer using a token returned by :func:`set_current_artifacts`."""
    _CURRENT.reset(token)


def save_artifact(
    name: str,
    obj: Any,
    *,
    format: Optional[str] = None,
) -> Any:
    """Save an artifact via the active writer. No-ops when no writer is active."""
    writer = _CURRENT.get()
    if not writer.enabled():
        return None
    return writer.save(name, obj, format=format)


def write_text(name: str, text: str) -> Any:
    """Save text via the active writer. No-ops when no writer is active."""
    writer = _CURRENT.get()
    if not writer.enabled():
        return None
    return writer.write_text(name, text)


def write_bytes(name: str, data: bytes) -> Any:
    """Save bytes via the active writer. No-ops when no writer is active."""
    writer = _CURRENT.get()
    if not writer.enabled():
        return None
    return writer.write_bytes(name, data)


def with_artifacts(fn: F) -> F:
    """Decorate a function so artifact saving "just works" inside its body.

    The wrapper accepts an optional ``artifacts=`` kwarg. When provided, it is
    parked in a ``ContextVar`` for the duration of the call; otherwise, the
    function inherits whatever writer is already active (e.g. one set by the
    worker). Either way, the decorated function does NOT need to declare an
    ``artifacts`` parameter -- it just calls :func:`save_artifact` directly.

    Example::

        @with_artifacts
        def error_budget(input_data, gate):
            report = compute(input_data, gate)
            save_artifact("output/error_report.json", report, format="json")
            save_artifact("output/ptm.npy", report["ptm"], format="numpy")
            return report
    """

    @wraps(fn)
    def wrapper(*args: Any, artifacts: Optional[ArtifactWriter] = None, **kwargs: Any) -> Any:
        if artifacts is None:
            return fn(*args, **kwargs)
        token = _CURRENT.set(artifacts)
        try:
            return fn(*args, **kwargs)
        finally:
            _CURRENT.reset(token)

    wrapper._accepts_artifacts = True  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]
