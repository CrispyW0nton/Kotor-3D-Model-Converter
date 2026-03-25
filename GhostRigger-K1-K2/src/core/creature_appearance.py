"""
creature_appearance.py — GhostRigger-K1-K2
==========================================
UTC creature appearance resolution pipeline.

Resolves a creature UTC (Creature Template) resource to the body model,
body texture override, head model, and head texture override by walking the
KotOR 2DA chain:

    UTC.appearance_id  →  appearance.2da row  →  body model name + texture
                                              →  normalhead column → heads.2da row → head model + tex

Reference chain
---------------
- PyKotor tools/creature.py  (get_body_model / get_head_model logic)
- KotOR.js ModuleCreature.ts (appearance_id → appearance.2da lookup)
- engine binary CSWSCreature::LoadModel (K1: 0x00439830, TSL: 0x004ba2e0)
  calls ProcessSkinSeams() at K1: 0x004392b6 / 0x00439986, TSL: 0x0044a920
- appearance.2da columns used:
    modeltype  – 'B' = bodyslot model, otherwise use 'race' directly
    modela/b/c/… – body model resrefs by armor variation slot
    texa/texb/…  – body texture prefix by armor slot
    racetex       – racially-derived texture prefix (fallback)
    normalhead    – row index into heads.2da for the default head
- heads.2da columns used:
    head          – head model resref
    headtexe/ve/vve/vvve – alignment-specific head texture overrides

Public API
----------
    resolve_utc_appearance(utc_gff_bytes, appearance_2da, heads_2da)
        → CreatureAppearance(body_model, body_tex, head_model, head_tex,
                             supermodel, scale)

    resolve_utc_appearance_from_library(resref, library, game='K1')
        → CreatureAppearance | None   (high-level: loads 2DAs automatically)

    merge_supermodel(child_model, parent_model)
        → KotorModel  (deep-copies parent bones into child; Phase 3.2)
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Lightweight UTC GFF reader (no external dependency)
# ─────────────────────────────────────────────────────────────────────────────

def _read_gff_field(data: bytes, field_type: int, field_data: bytes,
                    field_data_or_offset: int) -> Any:
    """Read a single GFF field value from raw bytes."""
    if field_type == 0:   return struct.unpack_from('<B', field_data, field_data_or_offset)[0]   # BYTE
    if field_type == 1:   return struct.unpack_from('<b', field_data, field_data_or_offset)[0]   # CHAR
    if field_type == 2:   return struct.unpack_from('<H', field_data, field_data_or_offset)[0]   # WORD
    if field_type == 3:   return struct.unpack_from('<h', field_data, field_data_or_offset)[0]   # SHORT
    if field_type == 4:   return struct.unpack_from('<I', field_data, field_data_or_offset)[0]   # DWORD
    if field_type == 5:   return struct.unpack_from('<i', field_data, field_data_or_offset)[0]   # INT
    if field_type == 8:   return struct.unpack_from('<f', field_data, field_data_or_offset)[0]   # FLOAT
    if field_type == 10:  # CExoString
        off = field_data_or_offset
        sz  = struct.unpack_from('<I', data, off)[0]
        return data[off+4 : off+4+sz].decode('ascii', errors='replace')
    if field_type == 11:  # ResRef (CResRef)
        off = field_data_or_offset
        sz  = struct.unpack_from('<B', data, off)[0]
        return data[off+1 : off+1+sz].decode('ascii', errors='replace')
    return None


class _GFFParser:
    """
    Minimal GFF parser that reads K1/K2 .utc (and any other GFF-format) files.
    Returns a flat dict of {label: value} for the top-level struct only
    (sufficient for UTC appearance fields).

    GFF spec reference:
    https://nwn.wiki/display/NWN1/GFF+(file+format)
    """

    def __init__(self, data: bytes):
        self._data = data
        self.fields: Dict[str, Any] = {}
        self._parse()

    def _parse(self):
        d = self._data
        if len(d) < 56:
            return
        # Header
        file_type    = d[0:4].decode('ascii', errors='replace').strip()
        # Offsets and counts
        struct_off   = struct.unpack_from('<I', d, 8)[0]
        struct_cnt   = struct.unpack_from('<I', d, 12)[0]
        field_off    = struct.unpack_from('<I', d, 16)[0]
        field_cnt    = struct.unpack_from('<I', d, 20)[0]
        label_off    = struct.unpack_from('<I', d, 24)[0]
        label_cnt    = struct.unpack_from('<I', d, 28)[0]
        fdata_off    = struct.unpack_from('<I', d, 32)[0]
        fdata_sz     = struct.unpack_from('<I', d, 36)[0]
        findx_off    = struct.unpack_from('<I', d, 40)[0]
        findx_sz     = struct.unpack_from('<I', d, 44)[0]

        # Read top-level struct (index 0): get its field indices
        if struct_cnt == 0 or struct_off + 12 > len(d):
            return
        s_type    = struct.unpack_from('<I', d, struct_off)[0]
        s_foffset = struct.unpack_from('<I', d, struct_off + 4)[0]
        s_fcount  = struct.unpack_from('<I', d, struct_off + 8)[0]

        # Collect field indices for the top-level struct
        if s_fcount == 1:
            fidx_list = [s_foffset]
        else:
            fidx_list = []
            base = findx_off + s_foffset
            for i in range(s_fcount):
                if base + i*4 + 4 > len(d):
                    break
                fidx_list.append(struct.unpack_from('<I', d, base + i*4)[0])

        # Read each field
        for fi in fidx_list:
            if fi >= field_cnt:
                continue
            fbase = field_off + fi * 12
            if fbase + 12 > len(d):
                continue
            ftype  = struct.unpack_from('<I', d, fbase)[0]
            lidx   = struct.unpack_from('<I', d, fbase + 4)[0]
            fval   = struct.unpack_from('<I', d, fbase + 8)[0]

            # Read label
            lbase = label_off + lidx * 16
            if lbase + 16 > len(d):
                continue
            label_raw = d[lbase:lbase+16].rstrip(b'\x00').decode('ascii', errors='replace')

            # Decode value
            try:
                # Simple types: value is stored in the DataOrDataOffset dword directly
                if ftype in (0, 1, 2, 3, 4, 5, 8):
                    # Reinterpret the 4-byte fval as the appropriate type
                    tmp = struct.pack('<I', fval)
                    if ftype == 0: val = struct.unpack('<B', tmp[:1])[0]
                    elif ftype == 1: val = struct.unpack('<b', tmp[:1])[0]
                    elif ftype == 2: val = struct.unpack('<H', tmp[:2])[0]
                    elif ftype == 3: val = struct.unpack('<h', tmp[:2])[0]
                    elif ftype == 4: val = struct.unpack('<I', tmp)[0]
                    elif ftype == 5: val = struct.unpack('<i', tmp)[0]
                    elif ftype == 8: val = struct.unpack('<f', tmp)[0]
                    else: val = fval
                elif ftype in (10, 11):
                    # String / ResRef: fval = offset into field data block
                    off = fdata_off + fval
                    if ftype == 10:   # CExoString
                        if off + 4 <= len(d):
                            sz = struct.unpack_from('<I', d, off)[0]
                            val = d[off+4 : off+4+sz].decode('ascii', errors='replace')
                        else:
                            val = ''
                    else:             # ResRef
                        if off + 1 <= len(d):
                            sz = struct.unpack_from('<B', d, off)[0]
                            val = d[off+1 : off+1+sz].decode('ascii', errors='replace')
                        else:
                            val = ''
                else:
                    val = fval  # complex types not needed for UTC fields
                self.fields[label_raw] = val
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
#  CreatureAppearance dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CreatureAppearance:
    """
    Resolved appearance for a creature UTC.

    body_model  : resref of the body MDL (e.g. 'p_bastilabb')
    body_tex    : texture override prefix (e.g. 'P_BastilaBB01') or None
    head_model  : resref of the head MDL (e.g. 'p_bastilahead') or None
    head_tex    : head texture override (e.g. 'P_BastilaBH') or None
    supermodel  : supermodel name from appearance.2da 'supermodel' col, or 'NULL'
    scale       : model scale factor (default 1.0)
    modeltype   : raw modeltype cell from appearance.2da ('B'=bodyslot, 'F'=full, etc.)
    race_model  : 'race' column value (full-body model for non-B modeltype)
    appearance_id : UTC appearance_id used for the lookup
    """
    body_model:    Optional[str] = None
    body_tex:      Optional[str] = None
    head_model:    Optional[str] = None
    head_tex:      Optional[str] = None
    supermodel:    str = 'NULL'
    scale:         float = 1.0
    modeltype:     str = ''
    race_model:    Optional[str] = None
    appearance_id: int = -1

    @property
    def primary_model(self) -> Optional[str]:
        """Return the single model resref to load (body_model for B-type, race_model otherwise)."""
        if self.modeltype == 'B':
            return self.body_model
        return self.race_model or self.body_model

    def __repr__(self):
        return (f"CreatureAppearance(id={self.appearance_id}, "
                f"modeltype={self.modeltype!r}, "
                f"primary={self.primary_model!r}, "
                f"body_tex={self.body_tex!r}, "
                f"head={self.head_model!r}, head_tex={self.head_tex!r})")


# ─────────────────────────────────────────────────────────────────────────────
#  Core resolution logic
# ─────────────────────────────────────────────────────────────────────────────

def resolve_utc_appearance(
    utc_gff_bytes: bytes,
    appearance_2da,                    # TwoDA object (from src.core.twoda)
    heads_2da=None,                    # TwoDA object or None
    alignment: int = 50,               # UTC.alignment (0–100; 50 = neutral)
    armor_bodyvar: Optional[str] = None,   # e.g. 'b' when wearing armor
    armor_tex_variation: int = 1,          # UTI.texture_variation (1–N)
) -> CreatureAppearance:
    """
    Resolve a creature UTC's appearance by reading the GFF fields and
    walking the appearance.2da / heads.2da lookup chain.

    Parameters
    ----------
    utc_gff_bytes     : raw bytes of the .utc GFF file
    appearance_2da    : TwoDA for 'appearance.2da' (src.core.twoda.TwoDA)
    heads_2da         : TwoDA for 'heads.2da', or None (head model skipped)
    alignment         : creature's alignment (0=darkside, 100=lightside, 50=neutral)
    armor_bodyvar     : armor slot letter ('a','b',…'j') when wearing armor,
                        or None for default/unarmored
    armor_tex_variation : UTI texture_variation index (1-based, rjust to 2 digits)

    Returns
    -------
    CreatureAppearance with resolved model/texture names
    """
    # ── Parse UTC GFF ────────────────────────────────────────────────────────
    gff = _GFFParser(utc_gff_bytes)
    f = gff.fields

    appearance_id = int(f.get('Appearance_Type', f.get('Appearance', -1)))
    if appearance_id < 0:
        log.warning("resolve_utc_appearance: no Appearance_Type field found")
        return CreatureAppearance(appearance_id=-1)

    # alignment from UTC: GFF field 'GoodEvil' (0=evil, 100=good)
    utc_alignment = int(f.get('GoodEvil', alignment))

    result = CreatureAppearance(appearance_id=appearance_id)

    # ── appearance.2da lookup ────────────────────────────────────────────────
    if appearance_2da is None or appearance_id >= len(appearance_2da):
        log.warning("resolve_utc_appearance: appearance_id %d out of range "
                    "(table has %d rows)", appearance_id, len(appearance_2da) if appearance_2da else 0)
        return result

    row = appearance_2da[appearance_id]

    # modeltype: 'B' = bodyslot (use modela/b/… + texa/b/…),
    #            'F' = full-body race model (use 'race' column directly),
    #            'S'/'P'/'C' = other full-body types
    modeltype = row.get('modeltype', '').strip().upper()
    result.modeltype = modeltype

    # supermodel
    result.supermodel = row.get('supermodel', 'NULL').strip() or 'NULL'

    # scale
    try:
        result.scale = float(row.get('modelscale', row.get('scale', '1.0')) or '1.0')
    except (ValueError, TypeError):
        result.scale = 1.0

    # race column (full-body model for non-B types)
    race_model = row.get('race', '').strip()
    result.race_model = race_model if race_model and race_model not in ('****', '') else None

    if modeltype != 'B':
        # Non-B: use 'race' column as the primary model; no body/head split
        log.debug("resolve_utc_appearance: modeltype=%r, using race model %r",
                  modeltype, result.race_model)
        return result

    # ── Bodyslot ('B') model + texture resolution ────────────────────────────
    # Determine model column and texture column from armor variation
    if armor_bodyvar and armor_bodyvar.strip() and armor_bodyvar.lower() not in ('', '****'):
        slot_letter = armor_bodyvar.lower()
        model_col = f'model{slot_letter}'
        # Alignment-based texture column
        is_evil = (utc_alignment <= 25)
        evil_col = f'tex{slot_letter}evil'
        # Check if evil column exists
        if is_evil and _col_exists(row, evil_col):
            tex_col = evil_col
        else:
            tex_col = f'tex{slot_letter}'
        tex_append = str(armor_tex_variation).rjust(2, '0')
    else:
        # Default / unarmored: modela + texa (or texaevil for evil alignment)
        model_col = 'modela'
        is_evil = (utc_alignment <= 25)
        if is_evil and _col_exists(row, 'texaevil'):
            tex_col = 'texaevil'
        else:
            tex_col = 'texa'
        tex_append = '01'

    body_model_raw = row.get(model_col, '').strip()
    tex_raw        = row.get(tex_col,   '').strip()

    # Fallback: if model_col is empty, try 'modela', then 'race'
    if not body_model_raw or body_model_raw == '****':
        body_model_raw = row.get('modela', '').strip()
    if not body_model_raw or body_model_raw == '****':
        body_model_raw = race_model or ''
    result.body_model = body_model_raw.lower() if body_model_raw and body_model_raw != '****' else None

    # Build override texture name: prefix + zero-padded variation index
    if tex_raw and tex_raw not in ('****', ''):
        body_tex = tex_raw + tex_append
        result.body_tex = body_tex.lower()
    else:
        # Try 'racetex' column as fallback
        racetex = row.get('racetex', '').strip()
        result.body_tex = (racetex.lower() + '01') if racetex and racetex != '****' else None

    log.debug("resolve_utc_appearance: id=%d modeltype=%r body=%r tex=%r",
              appearance_id, modeltype, result.body_model, result.body_tex)

    # ── Head model + texture resolution ─────────────────────────────────────
    if heads_2da is not None:
        normalhead_str = row.get('normalhead', '').strip()
        if normalhead_str and normalhead_str not in ('****', ''):
            try:
                normalhead_id = int(float(normalhead_str))
            except (ValueError, TypeError):
                normalhead_id = -1

            if normalhead_id >= 0 and normalhead_id < len(heads_2da):
                hrow = heads_2da[normalhead_id]
                head_model_raw = hrow.get('head', '').strip()
                result.head_model = head_model_raw.lower() if head_model_raw and head_model_raw != '****' else None

                # Head texture: alignment-based columns
                head_tex = None
                if utc_alignment < 10:
                    head_tex = hrow.get('headtexvvve', '').strip()
                elif utc_alignment < 20:
                    head_tex = hrow.get('headtexvve', '').strip()
                elif utc_alignment < 30:
                    head_tex = hrow.get('headtexve', '').strip()
                elif utc_alignment < 40:
                    head_tex = hrow.get('headtexe', '').strip()
                # TSL alternate texture (neutral/light-side)
                if not head_tex or head_tex in ('****', ''):
                    head_tex = hrow.get('alttexture', '').strip() or None
                result.head_tex = head_tex.lower() if head_tex and head_tex not in ('****', '') else None
                log.debug("resolve_utc_appearance: head=%r head_tex=%r",
                          result.head_model, result.head_tex)
    return result


def _col_exists(row, col: str) -> bool:
    """Return True if the TwoDA row has a non-empty, non-sentinel value for col."""
    val = row.get(col, '').strip()
    return bool(val) and val != '****'


# ─────────────────────────────────────────────────────────────────────────────
#  High-level library wrapper
# ─────────────────────────────────────────────────────────────────────────────

def resolve_utc_appearance_from_library(
    resref: str,
    library,
    game: str = 'K1',
) -> Optional[CreatureAppearance]:
    """
    High-level helper: load a UTC by resref from a GameLibrary, look up the
    appearance.2da and heads.2da, and return a CreatureAppearance.

    Parameters
    ----------
    resref  : creature resref, e.g. 'n_twilek01' or 'c_bantha'
    library : GameLibrary (src.resources.game_library or src.core.game_library_ext)
    game    : 'K1' or 'K2'

    Returns
    -------
    CreatureAppearance or None on failure
    """
    try:
        from .twoda import TwoDACache
        from .game_library_ext import RES_UTC
    except ImportError:
        log.error("resolve_utc_appearance_from_library: missing core imports")
        return None

    # Load UTC bytes
    utc_bytes = _load_resource_bytes(library, resref, RES_UTC, game)
    if utc_bytes is None:
        log.warning("resolve_utc_appearance_from_library: UTC '%s' not found", resref)
        return None

    # Load 2DA tables via TwoDACache
    cache = TwoDACache(library)
    appearance_2da = cache.get('appearance', game)
    heads_2da      = cache.get('heads',      game)

    if appearance_2da is None:
        log.warning("resolve_utc_appearance_from_library: appearance.2da not found")
        return None

    return resolve_utc_appearance(
        utc_bytes,
        appearance_2da,
        heads_2da,
    )


def _load_resource_bytes(library, resref: str, res_type: int, game: str) -> Optional[bytes]:
    """Load raw resource bytes from library for a given resref + type."""
    try:
        reader = (library._k1_key if game == 'K1' else library._k2_key)
        if reader is not None:
            entry = reader.get(resref.lower(), res_type)
            if entry is not None:
                return entry.read()
    except Exception as e:
        log.debug("_load_resource_bytes: %s", e)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.2 — Supermodel inheritance  (merge parent skeleton into child)
# ─────────────────────────────────────────────────────────────────────────────

def merge_supermodel(child_model, parent_model) -> Any:
    """
    Merge the parent skeleton (supermodel) into a child model (accessory).

    KotOR accessories (headpieces, armour bodies, cloaks) reference a
    supermodel such as 'S_Female02' or 'S_Male02'.  Their own MDL only
    contains the mesh nodes; the bone hierarchy lives in the supermodel.

    This function:
      1. Copies all bone/dummy nodes from the parent that are NOT already
         present in the child (by node name, case-insensitive).
      2. Wires them into the child's root hierarchy under the correct parent.
      3. Copies animation data from the parent for any bones that were added.
      4. Updates child_model.supermodel = parent_model.name (marks as merged).

    Parameters
    ----------
    child_model   : KotorModel (the accessory / body part)
    parent_model  : KotorModel (the supermodel / base skeleton)

    Returns
    -------
    The mutated child_model (same object, bones injected in-place).

    Notes
    -----
    - Skin-mesh vertex positions in accessories are stored in world/bone space
      by the NWN exporter, so no additional transform is needed after merge.
    - The child's mesh nodes that reference bones by name will automatically
      pick up the injected parent bones because all_nodes() DFS traversal
      visits them.
    - This mirrors the engine's CModelObject::SetSuperModel() call
      (K1: 0x004f9350, TSL: 0x005a1f70) which grafts parent bone transforms.

    Reference
    ---------
    KotOR.js OdysseyModel3D.loadSuperModel()  (src/three/odyssey/OdysseyModel3D.ts:150–400)
    KotorBlender io_scene_kotor/format/mdl/reader.py _merge_supermodel()
    PyKotor gl/models/read_mdl.py gl_load_stitched_model()
    """
    if child_model is None or parent_model is None:
        return child_model

    try:
        import copy

        # Collect existing child node names (case-insensitive) — used as the
        # duplicate-guard.  Re-collected after every batch insert so that
        # recursive calls do not re-inject already-present bones.
        child_names = {n.name.lower() for n in child_model.all_nodes()}

        # Guard: if the parent has already been fully merged (all its bones are
        # present in the child), skip to avoid duplicate-inject on refresh.
        parent_root = getattr(parent_model, 'root_node', None)

        # Find child root node early so we can abort cleanly.
        root = child_model.root_node
        if root is None:
            log.warning("merge_supermodel: child model has no root node")
            return child_model

        injected_count = 0

        def _is_bone_or_dummy(node) -> bool:
            """Return True if node is a bone or dummy (no geometry)."""
            if getattr(node, 'is_bone', False):
                return True
            return (not getattr(node, 'vertices', None) and
                    not getattr(node, 'verts', None))

        def _deep_copy_subtree(src_node, dst_parent, existing_names: set) -> int:
            """
            Recursively copy src_node's subtree (bones/dummies only) into
            dst_parent, skipping nodes whose names are already in existing_names.

            This preserves the full hierarchy of the parent skeleton rather than
            flattening everything to child root — which was the previous bug that
            caused bones to be injected at the wrong level and produced
            duplicates on repeated calls.

            Reference: KotorBlender _merge_supermodel() recursively traverses
            parent nodes and re-parents them under the matching child node.

            Returns the number of nodes injected.
            """
            count = 0
            for child in getattr(src_node, 'children', []):
                nname = child.name.lower() if child.name else ''
                if not _is_bone_or_dummy(child):
                    # Mesh nodes in the parent skeleton (e.g. body geometry) are
                    # never injected into the child — only bone hierarchy.
                    continue
                if nname in existing_names:
                    # Node already present: descend into its children so we can
                    # still pick up any *new* grandchildren.
                    # Find the matching node in the destination for correct parent.
                    dst_match = next(
                        (n for n in child_model.all_nodes()
                         if n.name.lower() == nname),
                        dst_parent,
                    )
                    count += _deep_copy_subtree(child, dst_match, existing_names)
                else:
                    # New bone: deep-copy the node (no geometry, just the node
                    # header fields) and wire it under dst_parent.
                    new_node = copy.copy(child)
                    new_node.children = []
                    new_node.parent = dst_parent
                    if not hasattr(dst_parent, 'children'):
                        dst_parent.children = []
                    dst_parent.children.append(new_node)
                    existing_names.add(nname)
                    log.debug("merge_supermodel: injected bone '%s' under '%s'",
                              child.name, dst_parent.name)
                    count += 1
                    # Recurse into the newly injected node for its children.
                    count += _deep_copy_subtree(child, new_node, existing_names)
            return count

        if parent_root is not None:
            # Walk parent tree starting from parent_root's children.
            # We pass child_names as a mutable set so recursion tracks newly
            # injected names and never double-injects on the same call.
            injected_count = _deep_copy_subtree(
                parent_root, root, child_names)

        if injected_count == 0:
            log.debug("merge_supermodel: no new bones to inject from '%s'",
                      getattr(parent_model, 'name', '?'))
        else:
            # Mark as merged
            child_model.supermodel = getattr(parent_model, 'name', child_model.supermodel)
            log.info("merge_supermodel: merged %d bones from '%s' into '%s'",
                     injected_count,
                     getattr(parent_model, 'name', '?'),
                     getattr(child_model,  'name', '?'))

    except Exception as exc:
        log.warning("merge_supermodel: failed — %s", exc, exc_info=True)

    return child_model


# ─────────────────────────────────────────────────────────────────────────────
#  Convenience: build appearance.2da + heads.2da from raw bytes
# ─────────────────────────────────────────────────────────────────────────────

def parse_appearance_tables(
    appearance_bytes: bytes,
    heads_bytes: Optional[bytes] = None,
):
    """
    Parse appearance.2da and optionally heads.2da from raw bytes.

    Returns (appearance_2da, heads_2da) as TwoDA objects.
    heads_2da may be None if heads_bytes is None.
    """
    from .twoda import TwoDA
    appearance_2da = TwoDA.from_bytes(appearance_bytes, name='appearance') if appearance_bytes else None
    heads_2da      = TwoDA.from_bytes(heads_bytes, name='heads') if heads_bytes else None
    return appearance_2da, heads_2da


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.4 — Supermodel animation inheritance
# ─────────────────────────────────────────────────────────────────────────────

def merge_supermodel_animations(child_model, parent_model) -> Any:
    """
    Copy animation clips from a parent (supermodel) into the child model for
    any animations the child does NOT already define by name.

    KotOR engine behaviour (from KotOR.js OdysseyModel3D.SuperModelLoader lines
    788–803):
      - The engine iterates the supermodel's animation list.
      - For each animation whose name is NOT in the child's animation map, the
        engine adds a reference to the supermodel's animation object.
      - This lets accessories (body parts, head models) play the same animation
        set as their base skeleton without duplicating keyframe data in every MDL.

    Parameters
    ----------
    child_model   : KotorModel  — the body/head/accessory model
    parent_model  : KotorModel  — the supermodel (skeleton source)

    Returns
    -------
    The mutated child_model (animations added in-place); same object.

    Reference
    ---------
    KotOR.js  OdysseyModel3D.SuperModelLoader (src/three/odyssey/OdysseyModel3D.ts)
    xoreos   src/engines/kotor/creature.cpp  setModel → supermodel chain
    """
    if child_model is None or parent_model is None:
        return child_model

    try:
        child_anims  = getattr(child_model,  'animations', None) or []
        parent_anims = getattr(parent_model, 'animations', None) or []

        if not parent_anims:
            return child_model

        # Build a set of animation names already in the child (case-insensitive)
        child_anim_names = {
            getattr(a, 'name', '').lower()
            for a in child_anims
        }

        import copy
        added = 0
        for anim in parent_anims:
            aname = getattr(anim, 'name', '').lower()
            if aname and aname not in child_anim_names:
                # Shallow-copy the animation so modifications to child don't
                # corrupt the parent's animation object
                child_anims.append(copy.copy(anim))
                child_anim_names.add(aname)
                added += 1

        if added:
            child_model.animations = child_anims
            log.info(
                "merge_supermodel_animations: copied %d animations from '%s' into '%s'",
                added,
                getattr(parent_model, 'name', '?'),
                getattr(child_model,  'name', '?'),
            )

    except Exception as exc:
        log.warning("merge_supermodel_animations: failed — %s", exc, exc_info=True)

    return child_model


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.3 — High-level UTC → loaded KotorModel pipeline
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CreatureModelSet:
    """
    Fully resolved and loaded KotorModel objects for a creature.

    Attributes
    ----------
    body_model      : loaded KotorModel for the body (primary model)
    head_model      : loaded KotorModel for the head, or None
    accessory_models: list of additional overlay KotorModels (cloaks, robes, etc.)
    appearance      : CreatureAppearance metadata
    merge_warnings  : list of non-fatal warning strings from the pipeline
    """
    body_model:       Any = None        # KotorModel or None
    head_model:       Any = None        # KotorModel or None
    accessory_models: List[Any] = field(default_factory=list)  # [KotorModel, ...]
    appearance:       Optional[CreatureAppearance] = None
    merge_warnings:   List[str] = field(default_factory=list)

    @property
    def primary(self):
        """Return body_model (the model to display in the viewport)."""
        return self.body_model

    def all_models(self) -> List[Any]:
        """Return all non-None models: body + accessories + head (in draw order)."""
        result = []
        if self.body_model is not None:
            result.append(self.body_model)
        for acc in (self.accessory_models or []):
            if acc is not None:
                result.append(acc)
        if self.head_model is not None:
            result.append(self.head_model)
        return result


def build_creature_model(
    utc_gff_bytes: bytes,
    library,
    game: str = 'K1',
    load_head: bool = True,
    merge_animations: bool = True,
    accessory_resrefs: Optional[List[str]] = None,
) -> Optional['CreatureModelSet']:
    """
    High-level pipeline: UTC GFF bytes → fully loaded CreatureModelSet.

    Steps
    -----
    1. Parse UTC GFF → appearance_id via resolve_utc_appearance().
    2. Load appearance.2da + heads.2da from library via TwoDACache.
    3. Resolve body model name, texture, head model name from 2DA chain.
    4. Load body MDL from library → KotorModel.
    5. Optionally load head MDL from library → KotorModel.
    6. Merge supermodel skeleton bones into body (merge_supermodel).
    7. Copy supermodel animations into body (merge_supermodel_animations).
    8. Optionally load each accessory_resrefs MDL (cloak/robe/headgear) and
       merge its skeleton so it shares the same bone hierarchy as the body,
       storing each as a separate KotorModel in result.accessory_models.
       This matches KotOR.js OdysseyModel3D.ts:780–803 supermodel stacking.
    9. Return CreatureModelSet with body, accessories, head, and metadata.

    Parameters
    ----------
    utc_gff_bytes     : raw .utc GFF file bytes
    library           : GameLibrary (src.core.game_library_ext or similar)
    game              : 'K1' or 'K2'
    load_head         : whether to load and return the head model
    merge_animations  : whether to copy parent animations into child
    accessory_resrefs : optional list of MDL resrefs to load as overlay layers
                        (e.g. cloak model, robe overlay, belt pouch)

    Returns
    -------
    CreatureModelSet, or None if the UTC GFF cannot be parsed.
    """
    try:
        from .twoda import TwoDACache
        from .game_library_ext import RES_MDL, RES_UTC
        from .mdl_parser import MDLBinaryParser
        from .model_data import GameVersion
    except ImportError as exc:
        log.error("build_creature_model: missing core import — %s", exc)
        return None

    warnings: List[str] = []

    # ── 1. Load 2DA tables ───────────────────────────────────────────────────
    cache = TwoDACache(library)
    appearance_2da = cache.get('appearance', game)
    heads_2da      = cache.get('heads',      game)

    if appearance_2da is None:
        log.warning("build_creature_model: appearance.2da not found in library")
        return None

    # ── 2. Resolve UTC appearance ────────────────────────────────────────────
    appearance = resolve_utc_appearance(
        utc_gff_bytes,
        appearance_2da,
        heads_2da,
    )

    if appearance.appearance_id < 0:
        log.warning("build_creature_model: could not determine appearance_id from UTC")
        return CreatureModelSet(appearance=appearance, merge_warnings=warnings)

    result = CreatureModelSet(appearance=appearance)

    # ── 3. Load body model ───────────────────────────────────────────────────
    primary_name = appearance.primary_model
    if primary_name:
        body_bytes = _load_mdl_bytes(library, primary_name, game)
        if body_bytes:
            try:
                parser = MDLBinaryParser(body_bytes, b'')
                body   = parser.parse()
                body.game_version = GameVersion.K1 if game == 'K1' else GameVersion.K2
                result.body_model = body
                log.debug("build_creature_model: loaded body '%s'", primary_name)
            except Exception as exc:
                w = f"body model parse error for '{primary_name}': {exc}"
                log.warning("build_creature_model: %s", w)
                warnings.append(w)
        else:
            w = f"body model '{primary_name}' not found in library"
            log.warning("build_creature_model: %s", w)
            warnings.append(w)

    # ── 4. Merge supermodel skeleton ─────────────────────────────────────────
    if result.body_model and appearance.supermodel and \
       appearance.supermodel.upper() not in ('NULL', '', 'NONE'):
        super_name = appearance.supermodel.lower()
        super_bytes = _load_mdl_bytes(library, super_name, game)
        if super_bytes:
            try:
                sparser = MDLBinaryParser(super_bytes, b'')
                smodel  = sparser.parse()
                smodel.game_version = GameVersion.K1 if game == 'K1' else GameVersion.K2
                merge_supermodel(result.body_model, smodel)
                if merge_animations:
                    merge_supermodel_animations(result.body_model, smodel)
            except Exception as exc:
                w = f"supermodel merge error for '{super_name}': {exc}"
                log.warning("build_creature_model: %s", w)
                warnings.append(w)
        else:
            log.debug("build_creature_model: supermodel '%s' not in library (may be expected)",
                      super_name)

    # ── 5. Load head model ───────────────────────────────────────────────────
    if load_head and appearance.head_model:
        head_name  = appearance.head_model.lower()
        head_bytes = _load_mdl_bytes(library, head_name, game)
        if head_bytes:
            try:
                hparser = MDLBinaryParser(head_bytes, b'')
                head    = hparser.parse()
                head.game_version = GameVersion.K1 if game == 'K1' else GameVersion.K2
                result.head_model = head
                log.debug("build_creature_model: loaded head '%s'", head_name)
            except Exception as exc:
                w = f"head model parse error for '{head_name}': {exc}"
                log.warning("build_creature_model: %s", w)
                warnings.append(w)
        else:
            log.debug("build_creature_model: head model '%s' not in library", head_name)

    # ── 6. Load accessory / overlay models (Phase 3.8c) ─────────────────────
    # Each entry in accessory_resrefs is an MDL resref for an overlay layer:
    # cloak, robe overlay, belt pouch, etc.  We load each one independently,
    # merge the body's supermodel skeleton into it (so shared bones animate
    # in sync), and store it in result.accessory_models for the viewport to
    # render on top of the body mesh.
    #
    # This mirrors KotOR.js OdysseyModel3D.ts:780–803 where the engine loads
    # additional 'wearable' models and binds them to the same skeleton as the
    # base body, then renders them as additional draw calls in the same frame.
    #
    # Reference: Kotor.NET CompositeModel; KotOR.js OdysseyModel3D.ts stacking.
    for acc_resref in (accessory_resrefs or []):
        acc_name  = acc_resref.lower().strip()
        if not acc_name:
            continue
        acc_bytes = _load_mdl_bytes(library, acc_name, game)
        if acc_bytes:
            try:
                aparser = MDLBinaryParser(acc_bytes, b'')
                acc_model = aparser.parse()
                acc_model.game_version = GameVersion.K1 if game == 'K1' else GameVersion.K2
                # Merge the body's already-merged supermodel bones into the
                # accessory so its skin mesh uses the same bone transforms.
                if result.body_model is not None:
                    merge_supermodel(acc_model, result.body_model)
                result.accessory_models.append(acc_model)
                log.debug("build_creature_model: loaded accessory '%s'", acc_name)
            except Exception as exc:
                w = f"accessory model parse error for '{acc_name}': {exc}"
                log.warning("build_creature_model: %s", w)
                warnings.append(w)
        else:
            w = f"accessory model '{acc_name}' not found in library"
            log.debug("build_creature_model: %s", w)
            warnings.append(w)

    result.merge_warnings = warnings
    return result


def _load_mdl_bytes(library, resref: str, game: str) -> Optional[bytes]:
    """Load raw MDL bytes for a model resref from the game library."""
    try:
        from .game_library_ext import RES_MDL
        reader = library._k1_key if game == 'K1' else library._k2_key
        if reader is None:
            return None
        entry = reader.get(resref.lower(), RES_MDL)
        if entry is not None:
            return entry.read()
    except Exception as exc:
        log.debug("_load_mdl_bytes '%s': %s", resref, exc)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.3  IPC integration hook  (called from main_window._ipc_open_utc)
# ─────────────────────────────────────────────────────────────────────────────

def load_utc_into_viewport(
    utc_resref: str,
    library,
    game: str = 'K1',
) -> Optional['CreatureModelSet']:
    """
    Convenience entry-point for main_window._ipc_open_utc:
    load a UTC creature template by resref and return a CreatureModelSet.

    If the UTC resref itself cannot be found (e.g. it was already resolved to a
    model resref by the caller) this returns None gracefully.

    Parameters
    ----------
    utc_resref : the creature template resref (e.g. 'n_twilek01')
    library    : GameLibrary
    game       : 'K1' or 'K2'
    """
    try:
        from .game_library_ext import RES_UTC
        reader = library._k1_key if game == 'K1' else library._k2_key
        if reader is None:
            return None
        entry = reader.get(utc_resref.lower(), RES_UTC)
        if entry is None:
            return None
        utc_bytes = entry.read()
        return build_creature_model(utc_bytes, library, game=game)
    except Exception as exc:
        log.warning("load_utc_into_viewport '%s': %s", utc_resref, exc)
        return None
