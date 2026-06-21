"""GPU viewport diagnostic probe helpers."""

from __future__ import annotations

import os

_GR_GPU_PROBE = os.environ.get("GHOSTRIGGER_VIEWPORT_PROBE", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
_GR_GPU_PROBE_SEEN: set = set()


def _gr_gpu_probe(node, wp, wo, is_id_rot: bool, composite_off=None) -> None:
    """Emit one GPU VBO transform probe when the viewport probe is enabled."""
    if not _GR_GPU_PROBE:
        return
    try:
        nl = (getattr(node, "name", "") or "").lower()
    except Exception:
        return
    if not getattr(node, "is_skin", False) or "head" not in nl:
        return
    key = (id(getattr(node, "_model_ref", None)), nl, id(node))
    if key in _GR_GPU_PROBE_SEEN:
        return
    _GR_GPU_PROBE_SEEN.add(key)
    import sys as _sys

    try:
        verts = getattr(node, "vertices", []) or []
        v0 = verts[0] if verts else (0.0, 0.0, 0.0)
        pos = tuple(round(float(x), 4) for x in getattr(node, "position", (0, 0, 0)))
        wpr = tuple(round(float(x), 4) for x in wp)
        wor = tuple(round(float(x), 4) for x in wo)
        v0r = tuple(round(float(x), 4) for x in v0)
        # Include composite_offset so the probe matches rendered position.
        cox = float(composite_off[0]) if composite_off is not None else 0.0
        coy = float(composite_off[1]) if composite_off is not None else 0.0
        coz = float(composite_off[2]) if composite_off is not None else 0.0
        ew = (
            float(v0[0]) + float(wp[0]) + cox,
            float(v0[1]) + float(wp[1]) + coy,
            float(v0[2]) + float(wp[2]) + coz,
        )
        co = None
        if composite_off is not None:
            co = tuple(round(float(x), 4) for x in composite_off)
        _sys.stderr.write(
            f"[GR-PROBE GPU-vbo] node={node.name} is_skin=True nvert={len(verts)}\n"
            f"  node.position       = {pos}\n"
            f"  world_transform     = wp={wpr}  wo={wor}  is_id_rot={is_id_rot}\n"
            f"  composite_offset    = {co}\n"
            f"  raw vertex[0]       = {v0r}\n"
            f"  expected world[0]   = ({ew[0]:.4f}, {ew[1]:.4f}, {ew[2]:.4f})\n"
        )
        _sys.stderr.flush()
    except Exception:
        pass


__all__ = ("_GR_GPU_PROBE", "_GR_GPU_PROBE_SEEN", "_gr_gpu_probe")
