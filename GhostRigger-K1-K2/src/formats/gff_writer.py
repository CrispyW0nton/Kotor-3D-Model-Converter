"""
GFF V3.2 binary writer for GhostRigger.

Serializes a GffFile back to bytes that KotOR / GModular can read.

Spec: BioWare Aurora GFF Format (nwn.wiki)

Strategy (two-pass):
  Pass 1: Walk the entire struct tree, collect all structs in BFS order,
          collect all unique labels.
  Pass 2: Assign sequential struct indices and field indices, then serialize.
"""
from __future__ import annotations

import io
import logging
import struct
from typing import Any, Dict, List, Optional, Tuple

from .gff_types import (
    GffFieldType, GffField, GffStruct, GffFile,
    LocString, ResRef,
)

log = logging.getLogger(__name__)

_INLINE_TYPES = {
    GffFieldType.BYTE,
    GffFieldType.CHAR,
    GffFieldType.UINT16,
    GffFieldType.INT16,
    GffFieldType.UINT32,
    GffFieldType.INT32,
    GffFieldType.FLOAT,
}


class GffWriter:
    """
    GFF V3.2 binary serializer.

    Usage:
        writer = GffWriter(gff_file)
        data: bytes = writer.serialize()
    """

    def __init__(self, gff: GffFile):
        self._gff = gff

    # ─── Public API ──────────────────────────────────────────────────────────

    def serialize(self) -> bytes:
        # Pass 1: collect all structs (BFS order) and unique labels
        all_structs: List[GffStruct] = []
        struct_idx: Dict[int, int] = {}  # id(struct) → index
        all_labels: List[str] = []
        label_idx: Dict[str, int] = {}

        def _collect(s: GffStruct):
            sid = id(s)
            if sid in struct_idx:
                return
            idx = len(all_structs)
            struct_idx[sid] = idx
            all_structs.append(s)
            for label, gf in s.fields.items():
                if label not in label_idx:
                    label_idx[label] = len(all_labels)
                    all_labels.append(label)
                if gf.type == GffFieldType.STRUCT and isinstance(gf.value, GffStruct):
                    _collect(gf.value)
                elif gf.type == GffFieldType.LIST and isinstance(gf.value, list):
                    for item in gf.value:
                        if isinstance(item, GffStruct):
                            _collect(item)

        _collect(self._gff.root)

        # Pass 2: assign field indices sequentially across all structs,
        # then build all output buffers

        # Assign field indices: iterate structs in order, then fields in order
        # struct_field_indices[struct_idx] = list of field indices
        struct_field_indices: List[List[int]] = []
        all_fields: List[GffField] = []
        field_counter = [0]

        for s in all_structs:
            fis = []
            for gf in s.fields.values():
                fi = field_counter[0]
                field_counter[0] += 1
                all_fields.append(gf)
                fis.append(fi)
            struct_field_indices.append(fis)

        # Build field data block and field entries
        fdata_buf    = io.BytesIO()
        field_entries = []  # list of (type_int, lbl_idx, data_or_off)
        findices_buf = io.BytesIO()
        lindices_buf = io.BytesIO()

        for i, gf in enumerate(all_fields):
            lbl_i = label_idx.get(gf.label, 0)
            data_or_off = self._encode_field(
                gf, fdata_buf, struct_idx, findices_buf, lindices_buf
            )
            field_entries.append((int(gf.type), lbl_i, data_or_off))

        # Build struct entries
        struct_entries = []  # list of (type_id, foff, fcnt)
        for si, s in enumerate(all_structs):
            fis = struct_field_indices[si]
            fcnt = len(fis)
            if fcnt == 0:
                foff = 0
            elif fcnt == 1:
                foff = fis[0]  # inline: foff is the field index
            else:
                # foff = byte offset into field_indices buffer
                foff = findices_buf.tell()
                # NOTE: findices_buf already has data from LIST fields;
                # we need to append the struct's field indices.
                # But if LIST fields wrote to findices_buf first, offsets would conflict.
                # Solution: use a separate struct_findices_buf and merge at the end.
                # Actually we need to be more careful here.
                foff = _STRUCT_FINDICES_PLACEHOLDER  # will fill below
                struct_entries.append((s.type_id, fis, fcnt))
                continue
            struct_entries.append((s.type_id, foff, fcnt))

        # Rebuild with proper findices handling (separate field indices for structs vs LIST)
        # Use a clean two-buffer approach:
        struct_findices_buf = io.BytesIO()
        final_struct_entries = []

        for si, s in enumerate(all_structs):
            fis = struct_field_indices[si]
            fcnt = len(fis)
            if fcnt == 0:
                foff = 0
            elif fcnt == 1:
                foff = fis[0]
            else:
                foff = struct_findices_buf.tell()
                for fi in fis:
                    struct_findices_buf.write(struct.pack('<I', fi))
            final_struct_entries.append((s.type_id, foff, fcnt))

        # For LIST fields, their list_indices offsets were written into lindices_buf
        # during _encode_field. For STRUCT fields, data_or_off is the struct index.
        # The field_indices block is only for multi-field struct entries — keep struct_findices.

        # Now build all byte sections
        struct_buf   = io.BytesIO()
        for type_id, foff, fcnt in final_struct_entries:
            struct_buf.write(struct.pack('<3I', type_id, foff, fcnt))

        field_buf = io.BytesIO()
        for ftype_int, lbl_i, doo in field_entries:
            field_buf.write(struct.pack('<3I', ftype_int, lbl_i, doo))

        label_buf = io.BytesIO()
        for lbl in all_labels:
            raw = lbl.encode('latin-1')[:16].ljust(16, b'\x00')
            label_buf.write(raw)

        struct_bytes      = struct_buf.getvalue()
        field_bytes       = field_buf.getvalue()
        label_bytes       = label_buf.getvalue()
        fdata_bytes       = fdata_buf.getvalue()
        findices_bytes    = struct_findices_buf.getvalue()
        lindices_bytes    = lindices_buf.getvalue()

        # Calculate offsets
        header_size  = 56
        struct_off   = header_size
        field_off    = struct_off   + len(struct_bytes)
        label_off    = field_off    + len(field_bytes)
        fdata_off    = label_off    + len(label_bytes)
        findices_off = fdata_off    + len(fdata_bytes)
        lindices_off = findices_off + len(findices_bytes)

        struct_cnt = len(struct_bytes) // 12
        field_cnt  = len(field_bytes)  // 12
        label_cnt  = len(label_bytes)  // 16

        hdr = struct.pack('<4s4s12I',
            self._gff.file_type.encode('latin-1')[:4].ljust(4, b' '),
            b'V3.2',
            struct_off,   struct_cnt,
            field_off,    field_cnt,
            label_off,    label_cnt,
            fdata_off,    len(fdata_bytes),
            findices_off, len(findices_bytes),
            lindices_off, len(lindices_bytes),
        )

        return (hdr + struct_bytes + field_bytes + label_bytes +
                fdata_bytes + findices_bytes + lindices_bytes)

    # ─── Field encoding ───────────────────────────────────────────────────────

    def _encode_field(
        self,
        gf: GffField,
        fdata: io.BytesIO,
        struct_idx: Dict[int, int],
        findices: io.BytesIO,  # unused now (struct findices handled separately)
        lindices: io.BytesIO,
    ) -> int:
        """Encode a field value. Returns data_or_off."""
        ftype = gf.type
        val   = gf.value

        # ── Inline types ──────────────────────────────────────────────────
        if ftype == GffFieldType.BYTE:
            return int(val or 0) & 0xFF
        if ftype == GffFieldType.CHAR:
            v = int(val or 0)
            return (v + 256) & 0xFF if v < 0 else v & 0xFF
        if ftype == GffFieldType.UINT16:
            return int(val or 0) & 0xFFFF
        if ftype == GffFieldType.INT16:
            v = int(val or 0)
            return (v + 0x10000) & 0xFFFF if v < 0 else v & 0xFFFF
        if ftype == GffFieldType.UINT32:
            return int(val or 0) & 0xFFFFFFFF
        if ftype == GffFieldType.INT32:
            v = int(val or 0)
            return (v + 0x100000000) & 0xFFFFFFFF if v < 0 else v & 0xFFFFFFFF
        if ftype == GffFieldType.FLOAT:
            packed = struct.pack('<f', float(val or 0.0))
            return struct.unpack('<I', packed)[0]

        # ── Complex types — stored in FieldData ───────────────────────────
        off = fdata.tell()

        if ftype == GffFieldType.UINT64:
            fdata.write(struct.pack('<Q', int(val or 0)))
        elif ftype == GffFieldType.INT64:
            fdata.write(struct.pack('<q', int(val or 0)))
        elif ftype == GffFieldType.DOUBLE:
            fdata.write(struct.pack('<d', float(val or 0.0)))
        elif ftype == GffFieldType.POSITION:
            v = val or (0.0, 0.0, 0.0)
            fdata.write(struct.pack('<3f', *v))
        elif ftype == GffFieldType.ROTATION:
            v = val or (0.0, 0.0, 0.0, 1.0)
            fdata.write(struct.pack('<4f', *v))
        elif ftype == GffFieldType.CEXOSTRING:
            s = (val or "").encode('latin-1', errors='replace')
            fdata.write(struct.pack('<I', len(s)))
            fdata.write(s)
        elif ftype == GffFieldType.RESREF:
            if isinstance(val, ResRef):
                s = val.value.encode('latin-1', errors='replace')[:16]
            else:
                s = str(val or "").encode('latin-1', errors='replace')[:16]
            fdata.write(bytes([len(s)]) + s)
        elif ftype == GffFieldType.CEXOLOCSTRING:
            self._encode_locstring(val, fdata)
        elif ftype == GffFieldType.BINARY:
            raw = val or b''
            fdata.write(struct.pack('<I', len(raw)))
            fdata.write(raw)
        elif ftype == GffFieldType.STRUCT:
            # data_or_off = struct index in the struct array
            if isinstance(val, GffStruct):
                return struct_idx.get(id(val), 0)
            return 0
        elif ftype == GffFieldType.LIST:
            # data_or_off = byte offset into list_indices buffer
            list_off = lindices.tell()
            items = val or []
            lindices.write(struct.pack('<I', len(items)))
            for item in items:
                if isinstance(item, GffStruct):
                    si = struct_idx.get(id(item), 0)
                    lindices.write(struct.pack('<I', si))
            return list_off
        else:
            log.warning(f"Unhandled GFF write type {ftype}")

        return off

    def _encode_locstring(self, val, fdata: io.BytesIO):
        loc = val if isinstance(val, LocString) else LocString()
        body = io.BytesIO()
        for lang_id, text in loc.strings.items():
            enc = text.encode('latin-1', errors='replace')
            body.write(struct.pack('<2I', lang_id, len(enc)))
            body.write(enc)
        body_bytes = body.getvalue()
        total_size = 8 + len(body_bytes)
        fdata.write(struct.pack('<I', total_size))
        fdata.write(struct.pack('<i', loc.strref))
        fdata.write(struct.pack('<I', len(loc.strings)))
        fdata.write(body_bytes)


# Sentinel (not actually used - kept for reference)
_STRUCT_FINDICES_PLACEHOLDER = 0xDEADBEEF


def write_gff(gff: GffFile) -> bytes:
    """Serialize a GffFile to bytes. Convenience wrapper."""
    return GffWriter(gff).serialize()
