"""Diagnostic probes for the viewport frame renderer."""

from __future__ import annotations

from .dependencies import *  # noqa: F401,F403

_GR_VIEWPORT_PROBE = os.environ.get('GHOSTRIGGER_VIEWPORT_PROBE', '').strip().lower() in ('1', 'true', 'yes', 'on')
_GR_VIEWPORT_PROBE_SEEN: set = set()

def _gr_probe(tag: str, node, wp, wo, is_id: bool) -> None:
    """One-shot per (tag, model_id, node_name) Step-6 diagnostic probe.

    Enabled only when env var GHOSTRIGGER_VIEWPORT_PROBE=1 is set.
    Fires for skin nodes whose name contains 'head' so we can verify the
    actual world-transform applied at render time matches the single
    translation contract.  Prints node.position, wp, wo, is_id, raw v[0],
    and the expected world position of v[0].  Total zero behaviour change
    when the env var is unset.
    """
    if not _GR_VIEWPORT_PROBE:
        return
    try:
        nl = (node.name or '').lower()
    except Exception:
        return
    if not getattr(node, 'is_skin', False) or 'head' not in nl:
        return
    key = (tag, id(getattr(node, '_model_ref', None)), nl, id(node))
    if key in _GR_VIEWPORT_PROBE_SEEN:
        return
    _GR_VIEWPORT_PROBE_SEEN.add(key)
    import sys as _sys
    try:
        verts = getattr(node, 'vertices', []) or []
        v0 = verts[0] if verts else (0.0, 0.0, 0.0)
        pos = tuple(round(float(x), 4) for x in getattr(node, 'position', (0,0,0)))
        wpr = tuple(round(float(x), 4) for x in wp)
        wor = tuple(round(float(x), 4) for x in wo)
        v0r = tuple(round(float(x), 4) for x in v0)
        ew = (float(v0[0]) + float(wp[0]),
              float(v0[1]) + float(wp[1]),
              float(v0[2]) + float(wp[2]))
        _sys.stderr.write(
            f"[GR-PROBE {tag}] node={node.name} is_skin={node.is_skin} nvert={len(verts)}\n"
            f"  node.position    = {pos}\n"
            f"  world_transform  = wp={wpr}  wo={wor}  is_id_rot={is_id}\n"
            f"  raw vertex[0]    = {v0r}\n"
            f"  expected world[0]= ({ew[0]:.4f}, {ew[1]:.4f}, {ew[2]:.4f})\n"
        )
        _sys.stderr.flush()
    except Exception:
        pass  # probe must never break rendering


__all__ = tuple(name for name in globals() if not name.startswith('__'))
