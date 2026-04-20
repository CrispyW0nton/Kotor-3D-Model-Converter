"""
GhostRigger — in-memory patches for PyKotor binary MDL reading.

PyKotor's ``_TrimeshHeader.read`` mis-parses the KotOR 2 tail (hologram read as
uint32 plus two phantom uint32s), which shifts ``mdx_data_offset`` and
``vertices_offset``.  ``MDLBinaryReader._load_node`` also rejects
``mdx_data_offset == 0`` even though zero is a valid MDX base offset.

These fixes are applied **only in process RAM** (monkey-patched methods on the
already-imported PyKotor module).  No writes to site-packages — read-only pip
trees remain valid.

Compatibility guards
--------------------
Both patches target very specific shapes of upstream PyKotor code:

* ``_TrimeshHeader.read`` must accept ``(self, reader, game)`` and the class
  must expose ``K1_SIZE`` / ``K2_SIZE`` size constants (the patch seeks past
  ``start_pos + expected`` using those values).
* ``MDLBinaryReader._load_node`` source must contain the exact string
  ``"and bin_node.trimesh.mdx_data_offset not in (0, 0xFFFFFFFF)"``.

If PyKotor ever refactors either of those surfaces, our patch silently loses
its effect and K2 models quietly render with the wrong MDX alignment.  To
avoid that, :func:`ensure_pykotor_mdl_binary_fixes` performs a strict
pre-flight check and logs an ``ERROR`` (not a debug warning) when any
expected shape is missing.  The caller can inspect :data:`_last_check` to
see a structured summary of what passed / failed.

Cross-references: KotOR.js ``OdysseyModelNodeMesh.ts``, KotorBlender ``reader.py``.
"""

from __future__ import annotations

import inspect
import logging
import textwrap
from typing import TYPE_CHECKING, Any, Dict

log = logging.getLogger(__name__)

_applied: bool = False

# Structured summary of the most recent compatibility check.  Populated by
# :func:`_check_pykotor_compat` so tests / diagnostics can assert on it.
_last_check: Dict[str, Any] = {
    'checked': False,
    'ok': False,
    'failures': [],
    'trimesh_read_params': None,
    'k1_size': None,
    'k2_size': None,
    'load_node_pattern_present': None,
}

# Expected parameter list for ``_TrimeshHeader.read``.  Order matters —
# our replacement below is positional-compatible with this exact layout.
_EXPECTED_READ_PARAMS: tuple = ('self', 'reader', 'game')

# Expected MDX-offset guard fragment in ``MDLBinaryReader._load_node``.
_EXPECTED_LOAD_NODE_PATTERN: str = (
    "and bin_node.trimesh.mdx_data_offset not in (0, 0xFFFFFFFF)"
)

if TYPE_CHECKING:
    from pykotor.common.misc import Game
    from pykotor.common.stream import BinaryReader
    from pykotor.resource.formats.mdl.io_mdl import _TrimeshHeader


def ensure_pykotor_mdl_binary_fixes() -> None:
    """Idempotent: patch PyKotor ``io_mdl`` once per process.

    Performs a strict pre-flight check first.  If PyKotor no longer matches
    the layout the patches assume (e.g. after an upstream upgrade), every
    failure is logged at ``ERROR`` level and the patch is NOT applied —
    running on a broken assumption is worse than running on stock PyKotor
    because it can produce silently corrupt K2 geometry.
    """
    global _applied
    if _applied:
        return
    try:
        from pykotor.resource.formats.mdl import io_mdl as _iom
    except Exception as exc:
        log.error(
            "ensure_pykotor_mdl_binary_fixes: cannot import "
            "pykotor.resource.formats.mdl.io_mdl — %s", exc,
        )
        return

    if not _check_pykotor_compat(_iom):
        log.error(
            "ensure_pykotor_mdl_binary_fixes: PyKotor compatibility check "
            "FAILED — patches NOT applied.  Binary MDL reads will use the "
            "stock PyKotor code path, which mis-parses the K2 trimesh tail "
            "and rejects mdx_data_offset==0.  Re-pin PyKotor or update this "
            "module.  Summary: %s", _last_check,
        )
        return

    try:
        _iom._TrimeshHeader.read = _ghostrigger_trimesh_read  # type: ignore[method-assign]
        _patch_load_node_mdx_zero(_iom)
        log.debug("ensure_pykotor_mdl_binary_fixes: applied (K2 trimesh tail + MDX offset 0)")
        _applied = True
    except Exception as exc:
        log.error(
            "ensure_pykotor_mdl_binary_fixes: applying patches failed — %s",
            exc, exc_info=True,
        )


def _check_pykotor_compat(_iom) -> bool:
    """Validate that PyKotor still exposes the surfaces the patches assume.

    Returns ``True`` when every expected shape is present, ``False`` otherwise.
    Populates :data:`_last_check` with a structured summary so diagnostic
    scripts and tests can print exactly what drifted.
    """
    failures: list[str] = []
    _last_check.update({
        'checked': True,
        'ok': False,
        'failures': failures,
        'trimesh_read_params': None,
        'k1_size': None,
        'k2_size': None,
        'load_node_pattern_present': None,
    })

    TH = getattr(_iom, '_TrimeshHeader', None)
    if TH is None:
        failures.append("_TrimeshHeader class not found in io_mdl")
    else:
        read_fn = getattr(TH, 'read', None)
        if read_fn is None:
            failures.append("_TrimeshHeader.read method not found")
        else:
            try:
                params = tuple(inspect.signature(read_fn).parameters)
            except (TypeError, ValueError) as exc:
                params = None
                failures.append(f"inspect.signature(_TrimeshHeader.read) failed: {exc}")
            _last_check['trimesh_read_params'] = params
            if params is not None and params != _EXPECTED_READ_PARAMS:
                failures.append(
                    f"_TrimeshHeader.read signature changed: expected "
                    f"{_EXPECTED_READ_PARAMS}, got {params}"
                )

        k1 = getattr(TH, 'K1_SIZE', None)
        k2 = getattr(TH, 'K2_SIZE', None)
        _last_check['k1_size'] = k1
        _last_check['k2_size'] = k2
        if not isinstance(k1, int) or k1 <= 0:
            failures.append(f"_TrimeshHeader.K1_SIZE missing or invalid ({k1!r})")
        if not isinstance(k2, int) or k2 <= 0:
            failures.append(f"_TrimeshHeader.K2_SIZE missing or invalid ({k2!r})")

    MR = getattr(_iom, 'MDLBinaryReader', None)
    if MR is None:
        failures.append("MDLBinaryReader class not found in io_mdl")
    else:
        load_fn = getattr(MR, '_load_node', None)
        if load_fn is None:
            failures.append("MDLBinaryReader._load_node method not found")
        else:
            try:
                src = inspect.getsource(load_fn)
            except (OSError, TypeError) as exc:
                src = None
                failures.append(f"inspect.getsource(_load_node) failed: {exc}")
            if src is not None:
                present = (_EXPECTED_LOAD_NODE_PATTERN in src)
                _last_check['load_node_pattern_present'] = present
                if not present:
                    failures.append(
                        "MDLBinaryReader._load_node: expected MDX-offset guard "
                        f"{_EXPECTED_LOAD_NODE_PATTERN!r} not present in source"
                    )

    ok = not failures
    _last_check['ok'] = ok
    return ok


def _ghostrigger_trimesh_read(self, reader: "BinaryReader", game: "Game") -> "_TrimeshHeader":
    """``_TrimeshHeader.read`` with corrected K2 tail (8-byte dirt/hologram + 2 pad).

    Kept aligned with PyKotor ``io_mdl._TrimeshHeader.read`` except for the
    ``game == Game.K2`` branch and comments.
    """
    # FRAGILE: this wholesale replacement tracks PyKotor's internal layout byte
    # for byte.  Any upstream refactor that reorders fields or renames a reader
    # method (``read_uint32`` / ``read_vector3`` / ``read_terminated_string``)
    # silently drops us out of alignment.  ``_check_pykotor_compat`` only
    # validates the public signature and the size constants — it cannot detect
    # a field-order change.  When upgrading PyKotor, diff
    # ``_TrimeshHeader.read`` against this function and keep them in lockstep.
    from pykotor.common.misc import Game as _Game
    from pykotor.resource.formats.mdl.io_mdl import _TrimeshHeader as TH

    start_pos = reader.position()
    self.function_pointer0 = reader.read_uint32()
    self.function_pointer1 = reader.read_uint32()
    self.offset_to_faces = reader.read_uint32()
    faces_count_raw = reader.read_uint32()
    if faces_count_raw > 0x7FFFFFFF:
        faces_count_raw = 0x7FFFFFFF
    self.faces_count = faces_count_raw
    faces_count2_raw = reader.read_uint32()
    if faces_count2_raw > 0x7FFFFFFF:
        faces_count2_raw = 0x7FFFFFFF
    self.faces_count2 = faces_count2_raw
    self.bounding_box_min = reader.read_vector3()
    self.bounding_box_max = reader.read_vector3()
    self.radius = reader.read_single()
    self.average = reader.read_vector3()
    self.diffuse = reader.read_vector3()
    self.ambient = reader.read_vector3()
    self.transparency_hint = reader.read_uint32()
    self.texture1 = reader.read_terminated_string("\0", 32)
    self.texture2 = reader.read_terminated_string("\0", 32)
    self.unknown0 = reader.read_bytes(24)
    self.offset_to_indices_counts = reader.read_uint32()
    indices_counts_count_raw = reader.read_uint32()
    if indices_counts_count_raw > 0x7FFFFFFF:
        indices_counts_count_raw = 0x7FFFFFFF
    self.indices_counts_count = indices_counts_count_raw
    indices_counts_count2_raw = reader.read_uint32()
    if indices_counts_count2_raw > 0x7FFFFFFF:
        indices_counts_count2_raw = 0x7FFFFFFF
    self.indices_counts_count2 = indices_counts_count2_raw
    self.offset_to_indices_offset = reader.read_uint32()
    indices_offsets_count_raw = reader.read_uint32()
    if indices_offsets_count_raw > 0x7FFFFFFF:
        indices_offsets_count_raw = 0x7FFFFFFF
    self.indices_offsets_count = indices_offsets_count_raw
    indices_offsets_count2_raw = reader.read_uint32()
    if indices_offsets_count2_raw > 0x7FFFFFFF:
        indices_offsets_count2_raw = 0x7FFFFFFF
    self.indices_offsets_count2 = indices_offsets_count2_raw
    self.offset_to_counters = reader.read_uint32()
    counters_count_raw = reader.read_uint32()
    if counters_count_raw > 0x7FFFFFFF:
        counters_count_raw = 0x7FFFFFFF
    self.counters_count = counters_count_raw
    counters_count2_raw = reader.read_uint32()
    if counters_count2_raw > 0x7FFFFFFF:
        counters_count2_raw = 0x7FFFFFFF
    self.counters_count2 = counters_count2_raw
    self.unknown1 = reader.read_bytes(12)
    self.saber_unknowns = reader.read_bytes(8)
    self.unknown2 = reader.read_int32()
    self.uv_direction = reader.read_vector2()
    self.uv_jitter = reader.read_single()
    self.uv_speed = reader.read_single()

    def _read_i32_as_u32() -> int:
        v: int = reader.read_int32()
        return 0xFFFFFFFF if v < 0 else v

    self.mdx_data_size = _read_i32_as_u32()
    self.mdx_data_bitmap = _read_i32_as_u32()
    self.mdx_vertex_offset = _read_i32_as_u32()
    self.mdx_normal_offset = _read_i32_as_u32()
    self.mdx_color_offset = _read_i32_as_u32()
    self.mdx_texture1_offset = _read_i32_as_u32()
    self.mdx_texture2_offset = _read_i32_as_u32()
    self.mdx_uv3_offset = _read_i32_as_u32()
    self.mdx_uv4_offset = _read_i32_as_u32()
    self.mdx_tangent_offset = _read_i32_as_u32()
    self.mdx_unknown_offset = _read_i32_as_u32()
    self.mdx_unknown2_offset = _read_i32_as_u32()
    self.mdx_unknown3_offset = _read_i32_as_u32()
    self.vertex_count = reader.read_uint16()
    self.texture_count = reader.read_uint16()
    self.has_lightmap = reader.read_uint8()
    self.rotate_texture = reader.read_uint8()
    self.background = reader.read_uint8()
    self.has_shadow = reader.read_uint8()
    self.beaming = reader.read_uint8()
    self.render = reader.read_uint8()
    if game == _Game.K2:
        # K2: 8-byte block (dirt + hologram) matching KotOR.js / KotorBlender, then 2 pad bytes.
        self.dirt_enabled = reader.read_uint8() != 0
        reader.read_uint8()  # padding
        self.dirt_texture = reader.read_int16()
        self.dirt_worldspace = reader.read_int16()
        self.hologram_donotdraw = reader.read_uint8() == 1
        reader.read_uint8()  # padding
        self.tail_short = 0
        self.k2_tail_long1 = 0
        self.k2_tail_long2 = 0
        reader.read_bytes(2)
    else:
        self.tail_short = reader.read_uint16()
    self.total_area = reader.read_single()
    self.tail_long0 = reader.read_uint32()
    self.mdx_data_offset = reader.read_uint32()
    self.vertices_offset = reader.read_uint32()
    expected = TH.K1_SIZE if game == _Game.K1 else TH.K2_SIZE
    reader.seek(start_pos + expected)
    return self


def _patch_load_node_mdx_zero(_iom) -> None:
    """Allow ``mdx_data_offset == 0`` (MDX data at start of buffer).

    The upstream pattern presence is validated up-front by
    :func:`_check_pykotor_compat`, so by the time we get here the replacement
    is guaranteed to match.  We still guard the string replacement so a stale
    Python ``inspect.getsource`` cache doesn't produce a silent no-op.
    """
    # FRAGILE: textual monkey-patching against a specific source string.
    # If PyKotor ever rewords the guard (e.g. to ``!= 0xFFFFFFFF``) this patch
    # becomes a no-op.  _check_pykotor_compat catches that at startup — do NOT
    # lower its failure to a debug log.
    src = inspect.getsource(_iom.MDLBinaryReader._load_node)
    src = textwrap.dedent(src)
    old = _EXPECTED_LOAD_NODE_PATTERN
    if old not in src:
        log.error(
            "GhostRigger PyKotor patch: _load_node MDX offset pattern missing "
            "at replace-time (compat check passed but source changed in between?). "
            "MDX offset 0 will still be rejected by PyKotor.",
        )
        return
    src = src.replace(old, "and bin_node.trimesh.mdx_data_offset != 0xFFFFFFFF", 1)
    code = compile(src, _iom.__file__, "exec")
    ns = _iom.__dict__
    exec(code, ns, ns)
    _iom.MDLBinaryReader._load_node = ns["_load_node"]  # type: ignore[method-assign]
