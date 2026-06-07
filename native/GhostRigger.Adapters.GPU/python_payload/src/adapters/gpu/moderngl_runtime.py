"""Optional ModernGL runtime dependencies for GPU adapters."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

try:
    import numpy as np

    _NUMPY = True
except ImportError:  # pragma: no cover - optional dependency
    np = None
    _NUMPY = False
    log.warning("gpu_renderer: numpy not available - GPU path disabled")

try:
    from PIL import Image

    _PIL = True
except ImportError:  # pragma: no cover - optional dependency
    Image = None
    _PIL = False
    log.warning("gpu_renderer: Pillow not available")

try:
    import moderngl

    _MODERNGL = True
except ImportError:  # pragma: no cover - optional dependency
    moderngl = None
    _MODERNGL = False
    log.info("gpu_renderer: moderngl not installed - GPU viewport rendering unavailable")

try:
    from core.animation.gpu_skinning import MatrixPaletteUploader, MAX_BONES as _SKIN_MAX_BONES

    _GPU_SKINNING = True
except ImportError:
    try:
        from src.core.animation.gpu_skinning import MatrixPaletteUploader, MAX_BONES as _SKIN_MAX_BONES

        _GPU_SKINNING = True
    except ImportError:  # pragma: no cover - optional skinning support
        MatrixPaletteUploader = None
        _GPU_SKINNING = False
        _SKIN_MAX_BONES = 128
        log.info("gpu_renderer: gpu_skinning module not available - skinning disabled")


__all__ = (
    "Image",
    "MatrixPaletteUploader",
    "_GPU_SKINNING",
    "_MODERNGL",
    "_NUMPY",
    "_PIL",
    "_SKIN_MAX_BONES",
    "moderngl",
    "np",
)
