"""
GhostRigger — in-memory patches for PyKotor binary MDL reading.

PyKotor's ``_TrimeshHeader.read`` mis-parses the KotOR 2 tail (hologram read as
uint32 plus two phantom uint32s), which shifts ``mdx_data_offset`` and
``vertices_offset``.  ``MDLBinaryReader._load_node`` also rejects
``mdx_data_offset == 0`` even though zero is a valid MDX base offset.

These fixes are applied **only in process RAM** (monkey-patched methods on the
already-imported PyKotor module).  No writes to site-packages — read-only pip
trees remain valid.

Cross-references: KotOR.js ``OdysseyModelNodeMesh.ts``, KotorBlender ``reader.py``.
"""

from __future__ import annotations

import inspect
import logging
import textwrap
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

_applied: bool = False

if TYPE_CHECKING:
    from pykotor.common.misc import Game
    from pykotor.common.stream import BinaryReader
    from pykotor.resource.formats.mdl.io_mdl import _TrimeshHeader


def ensure_pykotor_mdl_binary_fixes() -> None:
    """Idempotent: patch PyKotor ``io_mdl`` once per process."""
    global _applied
    if _applied:
        return
    try:
        from pykotor.resource.formats.mdl import io_mdl as _iom

        _iom._TrimeshHeader.read = _ghostrigger_trimesh_read  # type: ignore[method-assign]
        _patch_load_node_mdx_zero(_iom)
        log.debug("ensure_pykotor_mdl_binary_fixes: applied (K2 trimesh tail + MDX offset 0)")
        _applied = True
    except Exception as exc:
        log.warning("ensure_pykotor_mdl_binary_fixes: failed — %s", exc)


def _ghostrigger_trimesh_read(self, reader: "BinaryReader", game: "Game") -> "_TrimeshHeader":
    """``_TrimeshHeader.read`` with corrected K2 tail (8-byte dirt/hologram + 2 pad).

    Kept aligned with PyKotor ``io_mdl._TrimeshHeader.read`` except for the
    ``game == Game.K2`` branch and comments.
    """
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
    """Allow ``mdx_data_offset == 0`` (MDX data at start of buffer)."""
    src = inspect.getsource(_iom.MDLBinaryReader._load_node)
    src = textwrap.dedent(src)
    old = "and bin_node.trimesh.mdx_data_offset not in (0, 0xFFFFFFFF)"
    if old not in src:
        log.warning(
            "GhostRigger PyKotor patch: _load_node MDX offset pattern missing "
            "(PyKotor version changed?) — MDX offset 0 may still be rejected",
        )
        return
    src = src.replace(old, "and bin_node.trimesh.mdx_data_offset != 0xFFFFFFFF", 1)
    code = compile(src, _iom.__file__, "exec")
    ns = _iom.__dict__
    exec(code, ns, ns)
    _iom.MDLBinaryReader._load_node = ns["_load_node"]  # type: ignore[method-assign]
