from .compat import accepts_artifacts, call_with_optional_artifacts, supports_artifacts
from .noop import NoopArtifactWriter
from .protocol import ArtifactWriter

__all__ = [
    "ArtifactWriter",
    "NoopArtifactWriter",
    "accepts_artifacts",
    "call_with_optional_artifacts",
    "supports_artifacts",
]
