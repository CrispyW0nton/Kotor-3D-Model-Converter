"""Surgical MDL texture-reference patches for stock module room models."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from src.core.stock_modules.stock_module_materials import ModuleTextureReplacementDraft


_BASE = 12
_NODE_HEADER_SIZE = 80
_NODE_FLAG_MESH = 32
_MODEL_ROOT_OFFSET_ABS = _BASE + 40
_MODEL_NAME_TABLE_OFFSET_ABS = _BASE + 80 + 104
_MODEL_NAME_COUNT_ABS = _BASE + 80 + 108
_MESH_TEXTURE_OFFSET = 88
_MESH_LIGHTMAP_OFFSET = 120
_FIXED_STRING_SIZE = 32


@dataclass(frozen=True)
class ModuleMDLTexturePatchResult:
    room_resref: str
    node_name: str
    slot_kind: str
    original_texture_resref: str
    replacement_texture_resref: str
    texture_field_offset: int
    changed: bool = True

    @property
    def summary(self) -> str:
        return (
            f"{self.room_resref}.{self.node_name} {self.slot_kind}: "
            f"{self.original_texture_resref} -> {self.replacement_texture_resref}"
        )


@dataclass(frozen=True)
class _MeshTextureField:
    node_name: str
    node_offset: int
    texture_offset: int
    lightmap_offset: int
    texture_resref: str
    lightmap_resref: str


def patch_room_mdl_texture_reference(
    mdl_bytes: bytes,
    draft: ModuleTextureReplacementDraft,
) -> tuple[bytes, ModuleMDLTexturePatchResult]:
    """Patch one fixed-width trimesh diffuse texture field in a binary MDL."""

    if draft.target.slot_kind != "diffuse":
        raise ValueError("Only diffuse room texture MDL patches are supported.")
    replacement = _clean_resref(draft.replacement_texture_resref)
    original = _clean_resref(draft.original_texture_resref)
    target_node = _clean_resref(draft.target.node_name)
    if not replacement:
        raise ValueError("Replacement texture resref is empty.")
    if len(replacement) > 16:
        raise ValueError("Replacement texture resref exceeds 16 characters.")
    fields = [
        field
        for field in iter_mdl_texture_fields(mdl_bytes)
        if _clean_resref(field.node_name) == target_node and _clean_resref(field.texture_resref) == original
    ]
    if not fields:
        raise ValueError(
            f"Could not find {draft.target.room_resref}.{draft.target.node_name} "
            f"with diffuse texture {draft.original_texture_resref}."
        )
    if len(fields) > 1:
        raise ValueError(
            f"Texture patch target {draft.target.room_resref}.{draft.target.node_name} is ambiguous; "
            f"{len(fields)} matching mesh fields were found."
        )

    field = fields[0]
    patched = bytearray(mdl_bytes)
    _write_fixed_resref(patched, field.texture_offset, replacement)
    return bytes(patched), ModuleMDLTexturePatchResult(
        room_resref=draft.target.room_resref,
        node_name=field.node_name,
        slot_kind=draft.target.slot_kind,
        original_texture_resref=field.texture_resref,
        replacement_texture_resref=replacement,
        texture_field_offset=field.texture_offset,
    )


def iter_mdl_texture_fields(mdl_bytes: bytes) -> tuple[_MeshTextureField, ...]:
    """Return fixed texture/lightmap fields for mesh nodes in a binary MDL."""

    data = bytes(mdl_bytes)
    names = _read_name_table(data)
    root_rel = _read_u32(data, _MODEL_ROOT_OFFSET_ABS)
    root_abs = _to_abs_offset(data, root_rel)
    if root_abs is None:
        return ()
    fields: list[_MeshTextureField] = []
    stack = [root_abs]
    seen: set[int] = set()
    while stack:
        node_abs = stack.pop()
        if node_abs in seen or not _range_ok(data, node_abs, _NODE_HEADER_SIZE):
            continue
        seen.add(node_abs)
        type_id = _read_u16(data, node_abs)
        name_index = _read_u16(data, node_abs + 4)
        node_name = names[name_index] if 0 <= name_index < len(names) else f"node_{name_index}"
        if type_id & _NODE_FLAG_MESH:
            mesh_abs = node_abs + _NODE_HEADER_SIZE
            texture_offset = mesh_abs + _MESH_TEXTURE_OFFSET
            lightmap_offset = mesh_abs + _MESH_LIGHTMAP_OFFSET
            if _range_ok(data, texture_offset, _FIXED_STRING_SIZE) and _range_ok(data, lightmap_offset, _FIXED_STRING_SIZE):
                fields.append(
                    _MeshTextureField(
                        node_name=node_name,
                        node_offset=node_abs,
                        texture_offset=texture_offset,
                        lightmap_offset=lightmap_offset,
                        texture_resref=_read_fixed_resref(data, texture_offset),
                        lightmap_resref=_read_fixed_resref(data, lightmap_offset),
                    )
                )
        child_array_rel = _read_u32(data, node_abs + 44)
        child_count = min(_read_u32(data, node_abs + 48), 10000)
        child_array_abs = _to_abs_offset(data, child_array_rel)
        if child_array_abs is None or child_count <= 0:
            continue
        for index in range(child_count):
            child_rel_offset = child_array_abs + index * 4
            if not _range_ok(data, child_rel_offset, 4):
                break
            child_abs = _to_abs_offset(data, _read_u32(data, child_rel_offset))
            if child_abs is not None:
                stack.append(child_abs)
    return tuple(fields)


def _read_name_table(data: bytes) -> tuple[str, ...]:
    table_rel = _read_u32(data, _MODEL_NAME_TABLE_OFFSET_ABS)
    count = min(_read_u32(data, _MODEL_NAME_COUNT_ABS), 10000)
    table_abs = _to_abs_offset(data, table_rel)
    if table_abs is None or count <= 0:
        return ()
    names: list[str] = []
    for index in range(count):
        offset_abs = table_abs + index * 4
        if not _range_ok(data, offset_abs, 4):
            break
        string_abs = _to_abs_offset(data, _read_u32(data, offset_abs))
        if string_abs is None:
            names.append("")
        else:
            names.append(_read_c_string(data, string_abs))
    return tuple(names)


def _read_u16(data: bytes, offset: int) -> int:
    if not _range_ok(data, offset, 2):
        return 0
    return struct.unpack_from("<H", data, offset)[0]


def _read_u32(data: bytes, offset: int) -> int:
    if not _range_ok(data, offset, 4):
        return 0
    return struct.unpack_from("<I", data, offset)[0]


def _to_abs_offset(data: bytes, rel_offset: int) -> int | None:
    if rel_offset in (0, 0xFFFFFFFF):
        return None
    rel_abs = _BASE + rel_offset
    if 0 <= rel_abs < len(data):
        return rel_abs
    if 0 <= rel_offset < len(data):
        return rel_offset
    return None


def _range_ok(data: bytes | bytearray, offset: int, size: int) -> bool:
    return 0 <= offset <= len(data) and 0 <= size <= len(data) - offset


def _read_fixed_resref(data: bytes, offset: int) -> str:
    raw = data[offset:offset + _FIXED_STRING_SIZE]
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")


def _read_c_string(data: bytes, offset: int) -> str:
    end = data.find(b"\x00", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("ascii", errors="replace")


def _write_fixed_resref(data: bytearray, offset: int, value: str) -> None:
    if not _range_ok(data, offset, _FIXED_STRING_SIZE):
        raise ValueError("Texture field offset is outside the MDL payload.")
    encoded = value.encode("ascii", errors="replace")[:_FIXED_STRING_SIZE]
    data[offset:offset + _FIXED_STRING_SIZE] = encoded.ljust(_FIXED_STRING_SIZE, b"\x00")


def _clean_resref(value: object) -> str:
    return str(value or "").strip().strip("\x00").lower()


__all__ = [
    "ModuleMDLTexturePatchResult",
    "iter_mdl_texture_fields",
    "patch_room_mdl_texture_reference",
]
