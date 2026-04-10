"""
GFF V3.2 binary reader for GhostRigger.

Parses all KotOR GFF files: .utc .utp .utd .dlg .are .ifo .git etc.

Spec: BioWare Aurora GFF Format (nwn.wiki)
      xoreos C++ reference: github.com/xoreos/xoreos/blob/master/src/aurora/gff3file.cpp

Binary layout:
    [0..3]   FileType (e.g. "UTC ")
    [4..7]   FileVersion ("V3.2")
    [8..11]  StructOffset      (from file start)
    [12..15] StructCount
    [16..19] FieldOffset
    [20..23] FieldCount
    [24..27] LabelOffset
    [28..31] LabelCount
    [32..35] FieldDataOffset
    [36..39] FieldDataCount    (bytes)
    [40..43] FieldIndicesOffset
    [44..47] FieldIndicesCount (bytes)
    [48..51] ListIndicesOffset
    [52..55] ListIndicesCount  (bytes)

Struct entry (12 bytes):
    type_id      uint32
    field_offset uint32  (if count==1: field index; else: byte offset into FieldIndices)
    field_count  uint32

Field entry (12 bytes):
    type         uint32
    label_index  uint32
    data_or_off  uint32  (for simple types: data; for complex: byte offset into FieldData)

Label entry: 16 bytes, null-padded ASCII
"""
from __future__ import annotations

import io
import logging
import struct
from typing import Optional, List, Dict, Any, BinaryIO

from .gff_types import (
    GffFieldType, GffField, GffStruct, GffFile,
    LocString, ResRef,
)

log = logging.getLogger(__name__)

# Types stored inline in data_or_off (≤ 4 bytes)
_INLINE_TYPES = {
    GffFieldType.BYTE,
    GffFieldType.CHAR,
    GffFieldType.UINT16,
    GffFieldType.INT16,
    GffFieldType.UINT32,
    GffFieldType.INT32,
    GffFieldType.FLOAT,
}


class GffReader:
    """
    Binary GFF V3.2 parser.

    Usage:
        reader = GffReader(data: bytes)
        gff    = reader.parse()
    """

    def __init__(self, data: bytes):
        self._data = data
        self._buf  = io.BytesIO(data)

    # ─── Public API ──────────────────────────────────────────────────────────

    def parse(self) -> GffFile:
        buf = self._buf
        buf.seek(0)

        # Header (56 bytes)
        if len(self._data) < 56:
            raise ValueError("GFF data too short (< 56 bytes)")

        file_type    = buf.read(4).decode('latin-1')
        file_version = buf.read(4).decode('latin-1')

        if file_version not in ('V3.2', 'v3.2'):
            log.warning(f"Unexpected GFF version {file_version!r}, attempting parse anyway")

        (struct_off, struct_cnt,
         field_off,  field_cnt,
         label_off,  label_cnt,
         fdata_off,  fdata_cnt,
         findices_off, findices_cnt,
         lindices_off, lindices_cnt) = struct.unpack_from('<12I', buf.read(48))

        # Load the four main sections into memory
        labels      = self._read_labels(label_off, label_cnt)
        field_data  = self._read_bytes(fdata_off, fdata_cnt)
        field_inds  = self._read_bytes(findices_off, findices_cnt)
        list_inds   = self._read_bytes(lindices_off, lindices_cnt)

        # Parse struct headers (raw)
        structs_raw: List[tuple] = []
        for i in range(struct_cnt):
            off = struct_off + i * 12
            type_id, foff, fcnt = struct.unpack_from('<3I', self._data, off)
            structs_raw.append((type_id, foff, fcnt))

        # Pre-allocate all GffStruct objects so forward references resolve correctly
        resolved: List[GffStruct] = [GffStruct(type_id=t) for t, _, _ in structs_raw]

        # Parse fields (raw)
        fields_raw: List[tuple] = []
        for i in range(field_cnt):
            off = field_off + i * 12
            ftype, lbl_idx, data_or_off = struct.unpack_from('<3I', self._data, off)
            fields_raw.append((ftype, lbl_idx, data_or_off))

        # Resolve all structs into GffStruct objects
        # (resolved[] is pre-allocated so STRUCT fields that reference later indices work)
        for i, (type_id, foff, fcnt) in enumerate(structs_raw):
            gs = resolved[i]
            if fcnt == 1:
                fi = foff  # foff IS the field index
                gs.fields[labels[fields_raw[fi][1]]] = self._resolve_field(
                    fields_raw[fi], labels, field_data, resolved, field_inds, list_inds
                )
            elif fcnt > 1:
                for j in range(fcnt):
                    fi = struct.unpack_from('<I', field_inds, foff + j * 4)[0]
                    lbl = labels[fields_raw[fi][1]]
                    gs.fields[lbl] = self._resolve_field(
                        fields_raw[fi], labels, field_data, resolved, field_inds, list_inds
                    )

        root = resolved[0] if resolved else GffStruct()
        return GffFile(file_type=file_type, file_version=file_version, root=root)

    # ─── Private helpers ─────────────────────────────────────────────────────

    def _read_bytes(self, offset: int, count: int) -> bytes:
        if count == 0:
            return b''
        return self._data[offset: offset + count]

    def _read_labels(self, label_off: int, label_cnt: int) -> List[str]:
        labels = []
        for i in range(label_cnt):
            off = label_off + i * 16
            raw = self._data[off: off + 16]
            labels.append(raw.rstrip(b'\x00').decode('latin-1'))
        return labels

    def _resolve_field(
        self,
        field_raw: tuple,
        labels: List[str],
        field_data: bytes,
        resolved_structs: List[GffStruct],
        field_inds: bytes,
        list_inds: bytes,
    ) -> GffField:
        ftype_int, lbl_idx, data_or_off = field_raw
        label = labels[lbl_idx]
        try:
            ftype = GffFieldType(ftype_int)
        except ValueError:
            ftype = GffFieldType.UINT32
            log.warning(f"Unknown GFF field type {ftype_int} for label {label!r}")

        value = self._decode_field(ftype, data_or_off, field_data, resolved_structs, field_inds, list_inds)
        return GffField(label=label, type=ftype, value=value)

    def _decode_field(
        self,
        ftype: GffFieldType,
        data_or_off: int,
        field_data: bytes,
        resolved_structs: List[GffStruct],
        field_inds: bytes,
        list_inds: bytes,
    ) -> Any:
        D = data_or_off

        if ftype == GffFieldType.BYTE:
            return D & 0xFF
        if ftype == GffFieldType.CHAR:
            v = D & 0xFF
            return v if v < 128 else v - 256
        if ftype == GffFieldType.UINT16:
            return D & 0xFFFF
        if ftype == GffFieldType.INT16:
            v = D & 0xFFFF
            return v if v < 0x8000 else v - 0x10000
        if ftype == GffFieldType.UINT32:
            return D
        if ftype == GffFieldType.INT32:
            return D if D < 0x80000000 else D - 0x100000000
        if ftype == GffFieldType.FLOAT:
            return struct.unpack('<f', struct.pack('<I', D))[0]

        # Complex types (D = offset into field_data block)
        fd = field_data

        if ftype == GffFieldType.UINT64:
            return struct.unpack_from('<Q', fd, D)[0]
        if ftype == GffFieldType.INT64:
            return struct.unpack_from('<q', fd, D)[0]
        if ftype == GffFieldType.DOUBLE:
            return struct.unpack_from('<d', fd, D)[0]
        if ftype == GffFieldType.POSITION:
            x, y, z = struct.unpack_from('<3f', fd, D)
            return (x, y, z)
        if ftype == GffFieldType.ROTATION:
            x, y, z, w = struct.unpack_from('<4f', fd, D)
            return (x, y, z, w)

        if ftype == GffFieldType.CEXOSTRING:
            size = struct.unpack_from('<I', fd, D)[0]
            raw  = fd[D + 4: D + 4 + size]
            return raw.decode('latin-1', errors='replace')

        if ftype == GffFieldType.RESREF:
            size = fd[D] if D < len(fd) else 0
            raw  = fd[D + 1: D + 1 + size]
            return ResRef(raw.decode('latin-1', errors='replace'))

        if ftype == GffFieldType.CEXOLOCSTRING:
            total_size = struct.unpack_from('<I', fd, D)[0]
            strref     = struct.unpack_from('<i', fd, D + 4)[0]
            str_count  = struct.unpack_from('<I', fd, D + 8)[0]
            loc = LocString(strref=strref)
            pos = D + 12
            for _ in range(str_count):
                lang_id, str_size = struct.unpack_from('<2I', fd, pos)
                pos += 8
                text = fd[pos: pos + str_size].decode('latin-1', errors='replace')
                pos += str_size
                loc.strings[lang_id] = text
            return loc

        if ftype == GffFieldType.BINARY:
            size = struct.unpack_from('<I', fd, D)[0]
            return bytes(fd[D + 4: D + 4 + size])

        if ftype == GffFieldType.STRUCT:
            # D is the index into the resolved_structs list
            if D < len(resolved_structs):
                return resolved_structs[D]
            return GffStruct(type_id=D)

        if ftype == GffFieldType.LIST:
            # D is a byte offset into list_inds
            count = struct.unpack_from('<I', list_inds, D)[0]
            items = []
            for k in range(count):
                si = struct.unpack_from('<I', list_inds, D + 4 + k * 4)[0]
                if si < len(resolved_structs):
                    items.append(resolved_structs[si])
                else:
                    items.append(GffStruct(type_id=si))
            return items

        log.warning(f"Unhandled GFF field type {ftype}")
        return None


def read_gff(data: bytes) -> GffFile:
    """Parse GFF binary data and return a GffFile. Convenience wrapper."""
    return GffReader(data).parse()
