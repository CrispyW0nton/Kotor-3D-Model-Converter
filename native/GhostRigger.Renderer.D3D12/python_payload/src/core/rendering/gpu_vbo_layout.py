"""GPU VBO layout constants and pure attribute helpers."""

from __future__ import annotations

from typing import Tuple

try:
    import numpy as np

    _NUMPY = True
except ImportError:  # pragma: no cover - optional dependency
    np = None
    _NUMPY = False

_VBO_MAIN_FORMAT = "3f 3f 2f 2f 4f 4f"
_VBO_MAIN_ATTRS = ("in_pos", "in_norm", "in_uv", "in_uv_lm", "in_color", "in_weights")
_VBO_BONE_IDS_FORMAT = "4i"
_VBO_BONE_IDS_ATTRS = ("in_bone_ids",)


def _split_vbo_attributes_for_gpu(vdata: "np.ndarray") -> Tuple["np.ndarray", "np.ndarray"]:
    """Split legacy 22-float rows into float attributes plus int32 bone IDs."""
    if not _NUMPY:
        return None, None
    main = np.empty((len(vdata), 18), dtype=np.float32)
    main[:, 0:14] = vdata[:, 0:14]
    main[:, 14:18] = vdata[:, 18:22]  # weights remain float
    bone_ids = np.rint(vdata[:, 14:18]).astype(np.int32)
    return main, bone_ids


__all__ = (
    "_VBO_BONE_IDS_ATTRS",
    "_VBO_BONE_IDS_FORMAT",
    "_VBO_MAIN_ATTRS",
    "_VBO_MAIN_FORMAT",
    "_split_vbo_attributes_for_gpu",
)
