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
* ``MDLBinaryReader._load_node`` must exist.  When source is available, we also
  verify that it still contains the known upstream ``mdx_data_offset`` guard.

If PyKotor ever refactors either of those surfaces, an unapplied patch would
make K2 models quietly render with the wrong MDX alignment.  To avoid that,
:func:`ensure_pykotor_mdl_binary_fixes` performs a strict pre-flight check and
raises :class:`PyKotorPatchError` when any expected shape is missing.  The
caller can inspect :data:`_last_check` to see a structured summary of what
passed / failed.

``GHOSTRIGGER_ALLOW_UNPATCHED_PYKOTOR=1`` is a diagnostics-only escape hatch
for raw-PyKotor A/B comparisons and pre-bump validation runs.  Do not use it
for normal app startup or production model loading; bypassing this error can
reintroduce silent K2 geometry corruption.

Cross-references: KotOR.js ``OdysseyModelNodeMesh.ts``, KotorBlender ``reader.py``.
"""

from __future__ import annotations

import inspect
import logging
import os
from typing import TYPE_CHECKING, Any, Dict

log = logging.getLogger(__name__)

_applied: bool = False

# The patched reader is validated against PyKotor's current public constants.
# K2's binary mesh header is 340 bytes: the K1 2-byte tail field is replaced by
# a 10-byte K2 dirt/hologram block.
K1_SIZE: int = 332
K2_SIZE: int = 340

_ALLOW_UNPATCHED_ENV = "GHOSTRIGGER_ALLOW_UNPATCHED_PYKOTOR"


class _MdxDataOffsetZero(int):
    """Integer zero that bypasses PyKotor's invalid offset-0 guard."""

    def __new__(cls) -> "_MdxDataOffsetZero":
        return int.__new__(cls, 0)

    def __eq__(self, other: object) -> bool:
        if other == 0:
            return False
        return int.__eq__(self, other)

    def __hash__(self) -> int:
        return int.__hash__(self)


class PyKotorPatchError(RuntimeError):
    """Raised when GhostRigger cannot install its required PyKotor MDL patches.

    K2 models silently load with corrupt/empty geometry if the K2 trimesh patch
    does not apply.  Set ``GHOSTRIGGER_ALLOW_UNPATCHED_PYKOTOR=1`` only for
    diagnostics that intentionally compare against raw upstream PyKotor.
    """

# Structured summary of the most recent compatibility check.  Populated by
# :func:`_check_pykotor_compat` so tests / diagnostics can assert on it.
_last_check: Dict[str, Any] = {
    'checked': False,
    'ok': False,
    'status': 'not_checked',
    'detail': '',
    'bypassed': False,
    'applied': False,
    'failures': [],
    'trimesh_read_params': None,
    'k1_size': None,
    'k2_size': None,
    'load_node_pattern_present': None,
    'trimesh_read_source_matches': None,
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


def ensure_pykotor_mdl_binary_fixes() -> Dict[str, Any]:
    """Idempotent: patch PyKotor ``io_mdl`` once per process.

    Performs a strict pre-flight check first.  If PyKotor no longer matches
    the layout the patches assume (e.g. after an upstream upgrade), raises
    :class:`PyKotorPatchError` unless ``GHOSTRIGGER_ALLOW_UNPATCHED_PYKOTOR=1``
    is set for diagnostics.
    """
    global _applied
    if _applied:
        return dict(_last_check)
    try:
        from pykotor.resource.formats.mdl import io_mdl as _iom
    except Exception as exc:
        _last_check.update({
            'checked': True,
            'ok': False,
            'status': 'pykotor_missing',
            'detail': f"cannot import pykotor.resource.formats.mdl.io_mdl: {exc}",
            'failures': [str(exc)],
            'applied': False,
            'bypassed': False,
        })
        return _raise_or_bypass(_last_check)

    if not _check_pykotor_compat(_iom):
        return _raise_or_bypass(_last_check)

    try:
        _iom._TrimeshHeader.read = _ghostrigger_trimesh_read  # type: ignore[method-assign]
        _patch_load_node_mdx_zero(_iom)
        log.debug("ensure_pykotor_mdl_binary_fixes: applied (K2 trimesh tail + MDX offset 0)")
        _applied = True
        _last_check.update({
            'ok': True,
            'status': 'ok',
            'detail': '',
            'applied': True,
            'bypassed': False,
        })
    except Exception as exc:
        _last_check.update({
            'ok': False,
            'status': 'apply_failed',
            'detail': str(exc),
            'applied': False,
            'bypassed': False,
        })
        return _raise_or_bypass(_last_check)
    return dict(_last_check)


def _raise_or_bypass(result: Dict[str, Any]) -> Dict[str, Any]:
    """Raise for patch drift, with an explicit diagnostics-only bypass."""
    msg = (
        f"PyKotor K2 trimesh patch FAILED to install: {result.get('status', 'unknown')} "
        f"(detail: {result.get('detail') or '-'}). "
        "K2 models will load with corrupt geometry. "
        "Pin pykotor in requirements.txt to a validated version, "
        f"or set {_ALLOW_UNPATCHED_ENV}=1 to bypass for diagnostics only."
    )
    if os.environ.get(_ALLOW_UNPATCHED_ENV) == "1":
        result['bypassed'] = True
        log.error("%s  [BYPASSED via env var]", msg)
        return dict(result)
    raise PyKotorPatchError(msg)


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
        'status': 'not_checked',
        'detail': '',
        'bypassed': False,
        'applied': False,
        'failures': failures,
        'trimesh_read_params': None,
        'k1_size': None,
        'k2_size': None,
        'load_node_pattern_present': None,
        'trimesh_read_source_matches': None,
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
        if k1 != K1_SIZE:
            failures.append(f"_TrimeshHeader.K1_SIZE changed: expected {K1_SIZE}, got {k1!r}")
        if k2 != K2_SIZE:
            failures.append(f"_TrimeshHeader.K2_SIZE changed: expected {K2_SIZE}, got {k2!r}")

        if read_fn is not None:
            try:
                read_src = inspect.getsource(read_fn)
            except (OSError, TypeError) as exc:
                read_src = None
                _last_check['trimesh_read_source_matches'] = None
                log.debug("inspect.getsource(_TrimeshHeader.read) unavailable: %s", exc)
            if read_src is not None:
                source_matches = (
                    "hologram_value = reader.read_uint32()" in read_src
                    and "self.k2_tail_long1 = reader.read_uint32()" in read_src
                    and "self.k2_tail_long2 = reader.read_uint32()" in read_src
                )
                _last_check['trimesh_read_source_matches'] = source_matches
                if not source_matches:
                    failures.append(
                        "_TrimeshHeader.read source layout drifted from the "
                        "PyKotor K2 tail this monkey-patch replaces"
                    )

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
                _last_check['load_node_pattern_present'] = None
                log.debug("inspect.getsource(_load_node) unavailable: %s", exc)
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
    _last_check['status'] = 'ok' if ok else 'compat_failed'
    _last_check['detail'] = '; '.join(failures)
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
    mdx_data_offset = reader.read_uint32()
    self.mdx_data_offset = _MdxDataOffsetZero() if mdx_data_offset == 0 else mdx_data_offset
    self.vertices_offset = reader.read_uint32()
    expected = TH.K1_SIZE if game == _Game.K1 else TH.K2_SIZE
    reader.seek(start_pos + expected)
    return self


def _patch_load_node_mdx_zero(_iom) -> None:
    """Allow ``mdx_data_offset == 0`` without source rewriting.

    PyInstaller builds do not retain source files for ``inspect.getsource``.
    The replacement ``_TrimeshHeader.read`` stores offset 0 as
    ``_MdxDataOffsetZero`` so upstream arithmetic still seeks to byte 0 while
    PyKotor's ``not in (0, 0xFFFFFFFF)`` guard treats it as valid.
    """
    if getattr(_iom, "MDLBinaryReader", None) is None:
        raise RuntimeError("GhostRigger PyKotor patch: MDLBinaryReader missing")
