"""3j Step 1 - qBone/tBone byte-for-byte parity dump with per-skin-node provenance.

Triangulates three independent reads of qBone (4 floats / Vector4) and
tBone (3 floats / Vector3) per skin-node bone slot, with full provenance
captured so that the 3j-2 reference-engine replay can be aligned to the
exact same data pedigree without ambiguity:

    1. RAW BYTES    - struct.unpack at the absolute file offset
                      (offset_to_qbones + 12 in the MDL data section).
                      This is the on-disk ground truth.
    2. PYKOTOR      - skin._SkinmeshHeader.qbones[i] / .tbones[i] from the
                      GhostRiggerMDLBinaryReader (PyKotor MDL reader with
                      GhostRigger's K2 trimesh fix, the only reader path
                      production code uses via read_mdl_safe).
    3. GHOSTRIGGER  - gr.qbone_list[i] / gr.tbone_list[i] from
                      load_model_from_bytes (the model_data.MDLNode shape
                      that compute_skin_node_palette consumes at render
                      time).

The triple-parity output makes any divergence assignable to a specific
layer:

    1 != 2  =>  PyKotor decode error (offset, byte order, type)
    2 != 3  =>  GhostRigger consumption error in _read_skin_weights
    1 == 2 == 3  =>  import is faithful; the 3j defect must live in
                     interpretation (basis, handedness, composition order),
                     not in transcription. Sub-hypotheses B-qbone-basis-1
                     (basis-of-storage), B-qbone-basis-2 (handedness/order),
                     and B-qbone-basis-3 (relative-to-skin-bind) all
                     remain open.

Per-skin-node provenance captured (3j-1 user refinement):
    - skin_node_name, node_id (both reader pedigrees agree on this key)
    - mdl_field_offset_to_qbones, mdl_field_offset_to_tbones
        (raw uint32 values from the _SkinmeshHeader; data-section relative,
         which is what MDLOps and PyKotor both read directly via the +12
         BinaryReader offset adjustment)
    - mdl_field_qbones_count, mdl_field_qbones_count2,
      mdl_field_tbones_count, mdl_field_tbones_count2
    - file_absolute_offset_qbones, file_absolute_offset_tbones
        (== mdl_field_offset_to_X + 12; the actual byte offset inside
         mdl_bytes that struct.unpack consumes)
    - decode_path: short label describing the read path used for each
      of the three sources

Outputs (one JSONL per audited creature):

    diagnostics/skinning/2026_05/qbone_byte_parity_c_drexlf.jsonl
    diagnostics/skinning/2026_05/qbone_byte_parity_c_brith.jsonl
    diagnostics/skinning/2026_05/qbone_byte_parity_c_bomabeast.jsonl

Each JSONL has one record per skin-node-slot triple (qBone + tBone).
The first record per file is a ``_summary`` row aggregating divergences
across all slots in that creature.

Usage::

    python scripts/dump_qbone_byte_parity.py
"""

from __future__ import annotations

import json
import math
import struct
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

K1_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"
K2_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"

OUT_DIR = ROOT / "diagnostics" / "skinning" / "2026_05"

# 3j-1 ordering: c_drexlf and c_brith first (B-translation already
# eliminated by Step 7 math), c_bomabeast third (eliminated by visual
# gate but still useful as a third audit creature).
TARGETS: Tuple[Tuple[str, str, str], ...] = (
    ("c_drexlf",    "K2", "qbone_byte_parity_c_drexlf.jsonl"),
    ("c_brith",     "K2", "qbone_byte_parity_c_brith.jsonl"),
    ("c_bomabeast", "K1", "qbone_byte_parity_c_bomabeast.jsonl"),
)


# Convention from PyKotor io_mdl.py: BinaryReader has set_offset(+12)
# applied while reading MDL contents (the leading 12-byte file header
# is mdl_size/mdx_size/data_size). Therefore offsets stored on
# _SkinmeshHeader are relative to byte 12 of the file; the absolute
# file offset is the stored value plus 12.
MDL_DATA_SECTION_BASE = 12
QBONE_RECORD_SIZE = 16  # Vector4 = 4 * float32
TBONE_RECORD_SIZE = 12  # Vector3 = 3 * float32

# Floating-point parity tolerance. We expect EXACT bit-for-bit equality
# between raw bytes <-> PyKotor decode <-> GhostRigger consumption.
# A non-zero residual on any of the three pairs is itself the diagnostic
# signal, so the tolerance is set to 0.0 and any divergence is recorded.
PARITY_TOLERANCE_EXACT = 0.0


def _vec_or_obj_to_tuple(v: Any, n: int) -> Tuple[float, ...]:
    """Coerce PyKotor Vector3/Vector4 (or any sequence-like) into a tuple of n floats."""
    if v is None:
        return tuple([float("nan")] * n)
    out: List[float] = []
    for i, attr in enumerate(("x", "y", "z", "w")[:n]):
        try:
            out.append(float(getattr(v, attr, v[i])))
        except Exception:
            out.append(float("nan"))
    return tuple(out)


def _vec_max_abs_delta(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
    if len(a) != len(b):
        return float("inf")
    worst = 0.0
    for x, y in zip(a, b):
        if not (math.isfinite(x) and math.isfinite(y)):
            return float("inf")
        worst = max(worst, abs(x - y))
    return worst


def _read_raw_floats(buf: bytes, abs_offset: int, count: int) -> Tuple[float, ...]:
    """struct.unpack ``count`` little-endian float32 values starting at abs_offset."""
    end = abs_offset + count * 4
    if abs_offset < 0 or end > len(buf):
        return tuple([float("nan")] * count)
    return struct.unpack("<%df" % count, buf[abs_offset:end])


def _build_node_name_lookup_from_reader(reader: Any) -> Dict[int, str]:
    """Return ``node_id -> name`` map from MDLBinaryReader._names."""
    names = list(getattr(reader, "_names", []) or [])
    return {idx: str(n) for idx, n in enumerate(names)}


def _collect_pykotor_skin_provenance(
    reader: Any, mdl_bytes: bytes,
) -> List[Dict[str, Any]]:
    """Walk the binary nodes captured by the reader and return one
    provenance descriptor per skin-bearing node, in tree-walk order.

    Each descriptor includes raw header field values, derived absolute
    file offsets, and the PyKotor-decoded qbones/tbones slot list.
    """
    bin_nodes_by_offset = getattr(reader, "_gr_bin_nodes", None) or {}
    name_by_id = _build_node_name_lookup_from_reader(reader)

    descriptors: List[Dict[str, Any]] = []
    for file_node_offset in sorted(bin_nodes_by_offset.keys()):
        bin_node = bin_nodes_by_offset[file_node_offset]
        skin = getattr(bin_node, "skin", None)
        if skin is None:
            continue
        node_id = int(getattr(getattr(bin_node, "header", None), "node_id", -1))
        name = name_by_id.get(node_id, "")

        offset_to_qbones = int(getattr(skin, "offset_to_qbones", 0) or 0)
        qbones_count = int(getattr(skin, "qbones_count", 0) or 0)
        qbones_count2 = int(getattr(skin, "qbones_count2", 0) or 0)
        offset_to_tbones = int(getattr(skin, "offset_to_tbones", 0) or 0)
        tbones_count = int(getattr(skin, "tbones_count", 0) or 0)
        tbones_count2 = int(getattr(skin, "tbones_count2", 0) or 0)

        file_abs_qbones = (offset_to_qbones + MDL_DATA_SECTION_BASE
                           if offset_to_qbones not in (0, 0xFFFFFFFF) else None)
        file_abs_tbones = (offset_to_tbones + MDL_DATA_SECTION_BASE
                           if offset_to_tbones not in (0, 0xFFFFFFFF) else None)

        pk_qbones = list(getattr(skin, "qbones", []) or [])
        pk_tbones = list(getattr(skin, "tbones", []) or [])

        descriptors.append({
            "skin_node_name": name,
            "node_id": node_id,
            "node_file_offset": file_node_offset,
            "mdl_field_offset_to_qbones": offset_to_qbones,
            "mdl_field_qbones_count": qbones_count,
            "mdl_field_qbones_count2": qbones_count2,
            "mdl_field_offset_to_tbones": offset_to_tbones,
            "mdl_field_tbones_count": tbones_count,
            "mdl_field_tbones_count2": tbones_count2,
            "file_absolute_offset_qbones": file_abs_qbones,
            "file_absolute_offset_tbones": file_abs_tbones,
            "pykotor_qbones_decoded": [
                _vec_or_obj_to_tuple(q, 4) for q in pk_qbones
            ],
            "pykotor_tbones_decoded": [
                _vec_or_obj_to_tuple(t, 3) for t in pk_tbones
            ],
            "pykotor_qbones_decoded_count": len(pk_qbones),
            "pykotor_tbones_decoded_count": len(pk_tbones),
            "decode_path_pykotor": (
                "GhostRiggerMDLBinaryReader -> _SkinmeshHeader.read_extra "
                "(BinaryReader.read_vector4/read_vector3 at "
                "data-section-relative offset; reader has set_offset(+12) so "
                "stored offset is consumed directly)"
            ),
        })
    return descriptors


def _collect_ghostrigger_consumption(model: Any) -> Dict[str, Dict[str, Any]]:
    """Return ``skin_node_name -> {qbone_list, tbone_list, ...}``."""
    out: Dict[str, Dict[str, Any]] = {}
    for node in model.all_nodes():
        if not getattr(node, "is_skin", False):
            continue
        name = str(getattr(node, "name", "") or "")
        out[name] = {
            "ghostrigger_qbone_list": [
                tuple(float(c) for c in q) for q in (getattr(node, "qbone_list", []) or [])
            ],
            "ghostrigger_tbone_list": [
                tuple(float(c) for c in t) for t in (getattr(node, "tbone_list", []) or [])
            ],
            "ghostrigger_bone_map": list(getattr(node, "bone_map", []) or []),
            "decode_path_ghostrigger": (
                "load_model_from_bytes -> _read_skin_weights "
                "(getattr(skin,'qbones')/('tbones') consumed via "
                "Vector4.x/y/z/w / Vector3.x/y/z attribute access)"
            ),
        }
    return out


def _build_slot_record(
    *, resref: str, game: str, prov: Dict[str, Any], gr: Dict[str, Any],
    mdl_bytes: bytes, slot: int,
) -> Dict[str, Any]:
    """Build the per-slot triple-parity record for skin node + slot index."""

    # 1. Raw bytes -> qBone (4f)
    raw_q: Tuple[float, ...] = (float("nan"),) * 4
    file_abs_q_slot: Optional[int] = None
    if (
        prov["file_absolute_offset_qbones"] is not None
        and slot < prov["mdl_field_qbones_count"]
    ):
        file_abs_q_slot = prov["file_absolute_offset_qbones"] + slot * QBONE_RECORD_SIZE
        raw_q = _read_raw_floats(mdl_bytes, file_abs_q_slot, 4)

    # 1. Raw bytes -> tBone (3f)
    raw_t: Tuple[float, ...] = (float("nan"),) * 3
    file_abs_t_slot: Optional[int] = None
    if (
        prov["file_absolute_offset_tbones"] is not None
        and slot < prov["mdl_field_tbones_count"]
    ):
        file_abs_t_slot = prov["file_absolute_offset_tbones"] + slot * TBONE_RECORD_SIZE
        raw_t = _read_raw_floats(mdl_bytes, file_abs_t_slot, 3)

    # 2. PyKotor decoded
    pk_q = (
        prov["pykotor_qbones_decoded"][slot]
        if slot < len(prov["pykotor_qbones_decoded"])
        else (float("nan"),) * 4
    )
    pk_t = (
        prov["pykotor_tbones_decoded"][slot]
        if slot < len(prov["pykotor_tbones_decoded"])
        else (float("nan"),) * 3
    )

    # 3. GhostRigger consumed
    gr_q_list = gr.get("ghostrigger_qbone_list", [])
    gr_t_list = gr.get("ghostrigger_tbone_list", [])
    gr_q = (
        gr_q_list[slot] if slot < len(gr_q_list) else (float("nan"),) * 4
    )
    gr_t = (
        gr_t_list[slot] if slot < len(gr_t_list) else (float("nan"),) * 3
    )

    # Pairwise diffs
    raw_vs_pk_q = _vec_max_abs_delta(raw_q, pk_q)
    pk_vs_gr_q = _vec_max_abs_delta(pk_q, gr_q)
    raw_vs_gr_q = _vec_max_abs_delta(raw_q, gr_q)
    raw_vs_pk_t = _vec_max_abs_delta(raw_t, pk_t)
    pk_vs_gr_t = _vec_max_abs_delta(pk_t, gr_t)
    raw_vs_gr_t = _vec_max_abs_delta(raw_t, gr_t)

    bone_name = ""
    bm = gr.get("ghostrigger_bone_map", [])
    if slot < len(bm):
        bone_name = str(bm[slot] or "")

    return {
        "_kind": "slot_parity",
        "resref": resref,
        "game": game,
        "skin_node_name": prov["skin_node_name"],
        "node_id": prov["node_id"],
        "slot": slot,
        "bone_name_from_ghostrigger_bone_map": bone_name,
        "provenance": {
            "node_file_offset": prov["node_file_offset"],
            "mdl_field_offset_to_qbones": prov["mdl_field_offset_to_qbones"],
            "mdl_field_qbones_count": prov["mdl_field_qbones_count"],
            "mdl_field_qbones_count2": prov["mdl_field_qbones_count2"],
            "mdl_field_offset_to_tbones": prov["mdl_field_offset_to_tbones"],
            "mdl_field_tbones_count": prov["mdl_field_tbones_count"],
            "mdl_field_tbones_count2": prov["mdl_field_tbones_count2"],
            "file_absolute_offset_qbones_slot": file_abs_q_slot,
            "file_absolute_offset_tbones_slot": file_abs_t_slot,
            "decode_path_raw": (
                "struct.unpack('<4f' / '<3f', mdl_bytes[abs:abs+N]) at "
                "(mdl_field_offset_to_X + 12 + slot * record_size)"
            ),
            "decode_path_pykotor": prov["decode_path_pykotor"],
            "decode_path_ghostrigger": gr.get("decode_path_ghostrigger", ""),
        },
        "qbone": {
            "raw": list(raw_q),
            "pykotor": list(pk_q),
            "ghostrigger": list(gr_q),
            "raw_vs_pykotor_max_abs": raw_vs_pk_q,
            "pykotor_vs_ghostrigger_max_abs": pk_vs_gr_q,
            "raw_vs_ghostrigger_max_abs": raw_vs_gr_q,
            "raw_eq_pykotor": raw_vs_pk_q <= PARITY_TOLERANCE_EXACT,
            "pykotor_eq_ghostrigger": pk_vs_gr_q <= PARITY_TOLERANCE_EXACT,
            "raw_eq_ghostrigger": raw_vs_gr_q <= PARITY_TOLERANCE_EXACT,
        },
        "tbone": {
            "raw": list(raw_t),
            "pykotor": list(pk_t),
            "ghostrigger": list(gr_t),
            "raw_vs_pykotor_max_abs": raw_vs_pk_t,
            "pykotor_vs_ghostrigger_max_abs": pk_vs_gr_t,
            "raw_vs_ghostrigger_max_abs": raw_vs_gr_t,
            "raw_eq_pykotor": raw_vs_pk_t <= PARITY_TOLERANCE_EXACT,
            "pykotor_eq_ghostrigger": pk_vs_gr_t <= PARITY_TOLERANCE_EXACT,
            "raw_eq_ghostrigger": raw_vs_gr_t <= PARITY_TOLERANCE_EXACT,
        },
    }


def _classify_summary(slot_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-slot parity flags into a single classification."""
    n = len(slot_records)
    bad_raw_vs_pk_q = 0
    bad_pk_vs_gr_q = 0
    bad_raw_vs_pk_t = 0
    bad_pk_vs_gr_t = 0
    worst_raw_vs_pk_q = 0.0
    worst_pk_vs_gr_q = 0.0
    worst_raw_vs_pk_t = 0.0
    worst_pk_vs_gr_t = 0.0
    for rec in slot_records:
        q = rec["qbone"]
        t = rec["tbone"]
        if not q["raw_eq_pykotor"]:
            bad_raw_vs_pk_q += 1
        if not q["pykotor_eq_ghostrigger"]:
            bad_pk_vs_gr_q += 1
        if not t["raw_eq_pykotor"]:
            bad_raw_vs_pk_t += 1
        if not t["pykotor_eq_ghostrigger"]:
            bad_pk_vs_gr_t += 1
        worst_raw_vs_pk_q = max(worst_raw_vs_pk_q, q["raw_vs_pykotor_max_abs"])
        worst_pk_vs_gr_q = max(worst_pk_vs_gr_q, q["pykotor_vs_ghostrigger_max_abs"])
        worst_raw_vs_pk_t = max(worst_raw_vs_pk_t, t["raw_vs_pykotor_max_abs"])
        worst_pk_vs_gr_t = max(worst_pk_vs_gr_t, t["pykotor_vs_ghostrigger_max_abs"])

    if (bad_raw_vs_pk_q + bad_raw_vs_pk_t + bad_pk_vs_gr_q + bad_pk_vs_gr_t) == 0:
        classification = "import_faithful_defect_must_be_in_interpretation"
    elif (bad_raw_vs_pk_q + bad_raw_vs_pk_t) > 0:
        classification = "pykotor_decode_diverges_from_raw_bytes"
    else:
        classification = "ghostrigger_consumption_diverges_from_pykotor"

    return {
        "slots_total": n,
        "qbone_bad_raw_vs_pykotor": bad_raw_vs_pk_q,
        "qbone_bad_pykotor_vs_ghostrigger": bad_pk_vs_gr_q,
        "tbone_bad_raw_vs_pykotor": bad_raw_vs_pk_t,
        "tbone_bad_pykotor_vs_ghostrigger": bad_pk_vs_gr_t,
        "qbone_worst_raw_vs_pykotor_max_abs": worst_raw_vs_pk_q,
        "qbone_worst_pykotor_vs_ghostrigger_max_abs": worst_pk_vs_gr_q,
        "tbone_worst_raw_vs_pykotor_max_abs": worst_raw_vs_pk_t,
        "tbone_worst_pykotor_vs_ghostrigger_max_abs": worst_pk_vs_gr_t,
        "classification": classification,
        "interpretation": (
            "All three sources agree byte-for-byte. Import is faithful. "
            "The remaining 3j defect must live in interpretation, not "
            "transcription. Sub-hypotheses B-qbone-basis-1 (basis-of-storage), "
            "B-qbone-basis-2 (handedness/order), and B-qbone-basis-3 "
            "(relative-to-skin-bind) all remain open and are the next 3j-2 "
            "/ 3j-3 / 3j-4 audit targets."
            if classification == "import_faithful_defect_must_be_in_interpretation"
            else (
                "PyKotor decode diverges from raw MDL bytes; fix the loader "
                "before any further qBone interpretation work."
                if classification == "pykotor_decode_diverges_from_raw_bytes"
                else "GhostRigger consumption layer mangles PyKotor floats; "
                     "fix _read_skin_weights before any further qBone "
                     "interpretation work."
            )
        ),
    }


def _dump_one(rm: Any, resref: str, game: str, out_path: Path) -> int:
    from src.core.qt_core.mdl.ghostrigger_mdl_reader import GhostRiggerMDLBinaryReader
    from src.core.qt_core.game.kotor_loader import load_model_from_bytes

    mdl_bytes = rm.get_mdl(resref, game)
    if not mdl_bytes:
        print(f"[3j-1] ERR: {game}:{resref} MDL not found", file=sys.stderr)
        return 0
    mdx_bytes = rm.get_mdx(resref, game) or b""

    reader = GhostRiggerMDLBinaryReader(
        mdl_bytes, 0, len(mdl_bytes), mdx_bytes, 0, len(mdx_bytes),
    )
    try:
        _pykotor_mdl = reader.load()
    except Exception as exc:
        print(f"[3j-1] ERR: {game}:{resref} GhostRiggerMDLBinaryReader.load failed: {exc!r}",
              file=sys.stderr)
        return 0

    descriptors = _collect_pykotor_skin_provenance(reader, mdl_bytes)
    if not descriptors:
        print(f"[3j-1] WARN: {game}:{resref} no skin nodes found", file=sys.stderr)

    model = load_model_from_bytes(mdl_bytes, mdx_bytes)
    if model is None:
        print(f"[3j-1] ERR: {game}:{resref} load_model_from_bytes returned None",
              file=sys.stderr)
        return 0
    gr_skins = _collect_ghostrigger_consumption(model)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    slot_records: List[Dict[str, Any]] = []
    skin_node_records: List[Dict[str, Any]] = []
    for prov in descriptors:
        gr_consumption = gr_skins.get(prov["skin_node_name"], {
            "ghostrigger_qbone_list": [],
            "ghostrigger_tbone_list": [],
            "ghostrigger_bone_map": [],
            "decode_path_ghostrigger": (
                "ghostrigger model_data has no skin node with this name; "
                "_read_skin_weights may have rejected the skinmesh upstream"
            ),
        })

        per_node_records: List[Dict[str, Any]] = []
        slot_count = max(
            prov["mdl_field_qbones_count"],
            prov["mdl_field_tbones_count"],
            len(gr_consumption["ghostrigger_qbone_list"]),
            len(gr_consumption["ghostrigger_tbone_list"]),
        )
        for slot in range(slot_count):
            rec = _build_slot_record(
                resref=resref, game=game,
                prov=prov, gr=gr_consumption,
                mdl_bytes=mdl_bytes, slot=slot,
            )
            slot_records.append(rec)
            per_node_records.append(rec)
        skin_node_records.append({
            "_kind": "skin_node_summary",
            "resref": resref,
            "game": game,
            "skin_node_name": prov["skin_node_name"],
            "node_id": prov["node_id"],
            "node_file_offset": prov["node_file_offset"],
            "mdl_field_offset_to_qbones": prov["mdl_field_offset_to_qbones"],
            "mdl_field_qbones_count": prov["mdl_field_qbones_count"],
            "mdl_field_offset_to_tbones": prov["mdl_field_offset_to_tbones"],
            "mdl_field_tbones_count": prov["mdl_field_tbones_count"],
            "file_absolute_offset_qbones": prov["file_absolute_offset_qbones"],
            "file_absolute_offset_tbones": prov["file_absolute_offset_tbones"],
            "ghostrigger_qbone_list_count": len(gr_consumption["ghostrigger_qbone_list"]),
            "ghostrigger_tbone_list_count": len(gr_consumption["ghostrigger_tbone_list"]),
            "per_node_summary": _classify_summary(per_node_records),
        })

    summary = _classify_summary(slot_records)

    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_kind": "creature_summary",
            "_generated_by": "scripts/dump_qbone_byte_parity.py",
            "_generated_at": time.time(),
            "resref": resref,
            "game": game,
            "mdl_size_bytes": len(mdl_bytes),
            "mdx_size_bytes": len(mdx_bytes),
            "skin_nodes_total": len(descriptors),
            "summary": summary,
        }, sort_keys=True))
        fh.write("\n")
        for rec in skin_node_records:
            fh.write(json.dumps(rec, sort_keys=True))
            fh.write("\n")
        for rec in slot_records:
            fh.write(json.dumps(rec, sort_keys=True))
            fh.write("\n")

    print(
        f"[3j-1] {game}:{resref} -> {out_path.name}: "
        f"{len(descriptors)} skin nodes / {len(slot_records)} slot records / "
        f"{summary['classification']}"
    )
    return len(slot_records)


def main() -> int:
    from src.core.qt_core.assets.resource_manager import ResourceManager

    rm = ResourceManager()
    if not rm.set_k1_dir(K1_DIR):
        print(f"[3j-1] WARN: K1 dir not found: {K1_DIR}", file=sys.stderr)
    if not rm.set_k2_dir(K2_DIR):
        print(f"[3j-1] WARN: K2 dir not found: {K2_DIR}", file=sys.stderr)
    if not rm.is_ready():
        print("[3j-1] FATAL: no game install indexed", file=sys.stderr)
        return 2

    total = 0
    for resref, game, name in TARGETS:
        total += _dump_one(rm, resref, game, OUT_DIR / name)
    print(f"[3j-1] total slot records written: {total}")
    return 0 if total else 3


if __name__ == "__main__":
    raise SystemExit(main())
