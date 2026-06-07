"""ModernGL context factory adapter."""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

from src.core.rendering.gpu_diagnostics_config import _GL_BACKEND_ENV

log = logging.getLogger(__name__)

try:
    import moderngl
except ImportError:  # pragma: no cover - optional GPU dependency
    moderngl = None


def _gl_context_backend_candidates(os_name: Optional[str] = None) -> Tuple[str, ...]:
    """Return ModernGL standalone backend candidates for this platform."""
    override = os.environ.get(_GL_BACKEND_ENV, "").strip().lower()
    if override:
        return (override,)
    platform = os.name if os_name is None else os_name
    if platform == "nt":
        # Windows native standalone contexts are WGL; ModernGL's default path
        # resolves correctly there. Forcing EGL on Windows fails on common wheels.
        return ("default", "wgl", "egl")
    if platform == "posix":
        # Preserve the old headless Linux preference, with default/X11 fallbacks.
        return ("egl", "default", "x11")
    return ("default",)


def _create_moderngl_standalone_context():
    """Create a standalone ModernGL context using platform-appropriate backends."""
    if moderngl is None:
        raise RuntimeError("moderngl is not installed")
    failures = []
    for backend in _gl_context_backend_candidates():
        try:
            if backend == "default":
                return moderngl.create_standalone_context(), backend
            return moderngl.create_context(standalone=True, backend=backend), backend
        except Exception as exc:
            failures.append(f"{backend}: {exc}")
            log.debug("ModernGL backend %s failed: %s", backend, exc)
    raise RuntimeError("; ".join(failures) if failures else "no ModernGL backends attempted")


__all__ = ("_create_moderngl_standalone_context", "_gl_context_backend_candidates")
