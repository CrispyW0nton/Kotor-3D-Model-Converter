"""ModernGL context factory adapter."""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
from pathlib import Path
from typing import Optional, Tuple

from src.core.rendering.gpu_diagnostics_config import _GL_BACKEND_ENV

log = logging.getLogger(__name__)

_NATIVE_GPU_ADAPTER_ENV = "GHOSTRIGGER_ADAPTERS_GPU"
_NATIVE_GPU_ADAPTER_DLL = "GhostRigger.Adapters.Hardware.GPU.dll"

try:
    import moderngl
except ImportError:  # pragma: no cover - optional GPU dependency
    moderngl = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _native_gpu_adapter_candidates() -> Tuple[Path, ...]:
    override = os.environ.get(_NATIVE_GPU_ADAPTER_ENV, "").strip()
    if override:
        return (Path(override),)
    root = _repo_root()
    return (
        root / "build" / "vs" / "x64" / "Debug" / _NATIVE_GPU_ADAPTER_DLL,
        root / "build" / "vs" / "x64" / "Release" / _NATIVE_GPU_ADAPTER_DLL,
        root / "build" / "vs" / "Win32" / "Debug" / _NATIVE_GPU_ADAPTER_DLL,
        root / "build" / "vs" / "Win32" / "Release" / _NATIVE_GPU_ADAPTER_DLL,
        root / "native" / "GhostRigger.Adapters.Hardware.GPU" / "build" / "vs" / "x64" / "Debug" / _NATIVE_GPU_ADAPTER_DLL,
        root / "native" / "GhostRigger.Adapters.Hardware.GPU" / "build" / "vs" / "x64" / "Release" / _NATIVE_GPU_ADAPTER_DLL,
    )


def _python_gl_context_backend_candidates(os_name: Optional[str] = None) -> Tuple[str, ...]:
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


def _native_gl_context_backend_candidates(os_name: Optional[str] = None) -> Tuple[str, ...]:
    if platform.system() != "Windows":
        return ()
    existing = [path for path in _native_gpu_adapter_candidates() if path.exists()]
    if not existing:
        return ()
    try:
        dll = ctypes.CDLL(str(existing[0]))
        function = dll.gr_adapters_gpu_gl_backend_candidates_json
        function.argtypes = [ctypes.c_char_p]
        function.restype = ctypes.c_char_p
        raw = function((os.name if os_name is None else os_name).encode("utf-8"))
        values = json.loads((raw or b"[]").decode("utf-8", errors="replace"))
    except Exception as exc:
        log.debug("Native GPU adapter backend candidate query failed: %s", exc)
        return ()
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        return ()
    return tuple(value for value in values if value)


def _gl_context_backend_candidates(os_name: Optional[str] = None) -> Tuple[str, ...]:
    """Return ModernGL standalone backend candidates for this platform."""
    if os.environ.get(_GL_BACKEND_ENV, "").strip():
        return _python_gl_context_backend_candidates(os_name)
    native_candidates = _native_gl_context_backend_candidates(os_name)
    if native_candidates:
        return native_candidates
    return _python_gl_context_backend_candidates(os_name)


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
