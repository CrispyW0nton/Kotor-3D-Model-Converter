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
    appearance_2da,                    # 2DA object (from src.core.twoda)
    heads_2da=None,                    # 2DA object or None
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
    appearance_2da    : 2DA for 'appearance.2da' (src.core.twoda.2DA)
    heads_2da         : 2DA for 'heads.2da', or None (head model skipped)
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
    """Return True if the 2DA row has a non-empty, non-sentinel value for col."""
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
        from ..templates.twoda import TwoDACache
        from ..game.game_library_ext import RES_UTC
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

    Returns (appearance_2da, heads_2da) as 2DA objects.
    heads_2da may be None if heads_bytes is None.
    """
    from ..templates.twoda import TwoDA
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
        from ..templates.twoda import TwoDACache
        from ..game.game_library_ext import RES_MDL, RES_UTC
        from ..game.kotor_loader import load_model_from_bytes
        from ..geometry.model_data import GameVersion
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
                body   = load_model_from_bytes(body_bytes, b'')
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
                smodel  = load_model_from_bytes(super_bytes, b'')
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
                head    = load_model_from_bytes(head_bytes, b'')
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
                acc_model = load_model_from_bytes(acc_bytes, b'')
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
        from ..game.game_library_ext import RES_MDL
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
        from ..game.game_library_ext import RES_UTC
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


# ─────────────────────────────────────────────────────────────────────────────
#  Character Builder — Authentic KotOR Head-Body Assembly  (Phase 30)
#
#  How the Aurora engine (KotOR 1 & 2) actually attaches heads to bodies
#  -----------------------------------------------------------------------
#  Source: xoreos/src/engines/kotor/creature.cpp + model.cpp
#
#  1.  The engine loads the body MDL as a complete Model object.
#  2.  The engine loads the head MDL as a separate, independent Model object.
#  3.  It calls  body->attachModel("headhook", headModel)
#      which stores the head model as a pointer on the body's "headhook" node.
#      NO geometry merging, NO vertex translation, NO animation copying.
#  4.  During rendering the headhook node's world-space transform is used as
#      the parent matrix for the head model's render pass.
#  5.  Animations stay in sync because BOTH models set the SAME supermodel
#      in their MDL header (e.g. S_Female02 for K1, S_Female02/c_female02 for K2).
#      The engine walks the supermodel chain independently for each model.
#  6.  The "headhook" node name is EXACT — no aliases exist in real game files.
#
#  Standard KotOR supermodel chains
#  ---------------------------------
#  K1 male   : Body → S_Female02 → S_Female01 → S_Male02 → S_Male01
#  K1 female : Body → S_Female03 → S_Female02 → S_Female01 → S_Male02 → S_Male01
#  K2 male   : Body → S_Female02 → S_Female01 → S_Male02 → S_Male01
#  K2 female : Body → S_Female03 → S_Female02 → (same chain)
#  K2 alt    : c_female02 (cleanest K2 biped rig, used by GhostRigger templates)
#
#  GhostRigger Character Builder modes
#  -------------------------------------
#  CreatureAssembly (preview)  – keeps body + head as separate model objects
#      joined at the headhook node, matching the runtime engine exactly.
#      Use this for viewport preview.
#
#  snap_head_onto_body (viewport merge)  – physically grafts the head's root
#      node as a child of the headhook node (no vertex movement, no scaling,
#      no animation merging).  For a fast single-model viewport representation.
#
#  export_creature_separate (Option B1)  – validates the pair and returns both
#      MDL objects ready to write as TWO separate files, exactly as the game
#      expects.  Checks / fixes the supermodel reference on both models.
#
# ─────────────────────────────────────────────────────────────────────────────

# ── Supermodel chains (K1 & K2) ──────────────────────────────────────────────
# These are the only valid supermodel references for player-character / NPC
# humanoid rigs.  Both body AND head must reference the same entry.
_K1_SUPERMODELS = {
    'male':    's_female02',   # K1 male bodies/heads both use S_Female02 as root
    'female':  's_female03',   # K1 female bodies reference S_Female03 (lowest in chain)
    'default': 's_female02',   # safe default for unknown gender
}
_K2_SUPERMODELS = {
    'male':    's_female02',   # K2 male — same chain as K1
    'female':  's_female03',   # K2 female
    'default': 's_female02',   # safe default
    'alt':     'c_female02',   # K2 alternative clean rig
}

# The ONE real headhook node name used by the Aurora engine (exact, case-sensitive
# in binary MDL; we compare lower-case for robustness).
_HEADHOOK_NODE_NAME = 'headhook'

# Fallback names (non-standard / custom models only — always log a warning).
# Ordered by specificity: more specific attachment-point names come first.
# NOTE: generic skeleton bones like 'Neck' are intentionally excluded — a
# standard KotOR skeleton always has a Neck *bone*, but the headhook is a
# dedicated dummy/helper node placed at the top of that bone.  Matching 'neck'
# would cause false positives on every body model.
_HEADHOOK_FALLBACKS = (
    'head_hook',   # common modder alias
    'headpoint',   # used by some custom rigs
    'head_point',
    'headnode',
    'head_node',
    'neckjoint',   # explicit joint marker (not a generic skeleton bone)
)


def _find_headhook_node(model, strict: bool = False):
    """
    Locate the 'headhook' attachment node in a body model.

    Search strategy
    ---------------
    1. First pass: exact match for 'headhook' (case-insensitive).
    2. If strict=True, stop here — return None if not found.
    3. Second pass: iterate fallback names in priority order; for each
       fallback name, scan ALL nodes looking for an exact match.  This
       ensures the more-specific fallbacks (e.g. 'headpoint') are tested
       before less-specific ones, regardless of the node iteration order
       in the model's flat list.

    Parameters
    ----------
    model  : KotorModel
    strict : if True, only accept the exact name 'headhook' (no fallbacks)

    Returns
    -------
    (node, used_fallback: bool)  –  node is None if not found
    """
    try:
        all_nodes = list(model.all_nodes())

        # ── Pass 1: exact 'headhook' ──────────────────────────────────────
        for node in all_nodes:
            if node.name.lower() == _HEADHOOK_NODE_NAME:
                return node, False

        if strict:
            return None, False

        # ── Pass 2: fallbacks, highest-priority first ─────────────────────
        # Build a lower-case name → node map for O(1) lookup per fallback.
        node_by_name = {}
        for node in all_nodes:
            nl = node.name.lower()
            if nl not in node_by_name:          # keep first occurrence
                node_by_name[nl] = node

        for fb in _HEADHOOK_FALLBACKS:
            match = node_by_name.get(fb)
            if match is not None:
                log.warning(
                    "_find_headhook_node: body '%s' uses non-standard "
                    "headhook name '%s' — real game uses 'headhook'",
                    model.name, match.name,
                )
                return match, True

    except Exception:
        pass
    return None, False


def _world_pos_of_node(node) -> tuple:
    """Accumulate world-space position by walking parent chain."""
    pos = list(getattr(node, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
    p = getattr(node, 'parent', None)
    visited = set()
    while p is not None and id(p) not in visited:
        visited.add(id(p))
        pp = getattr(p, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
        pos[0] += pp[0]; pos[1] += pp[1]; pos[2] += pp[2]
        p = getattr(p, 'parent', None)
    return tuple(pos)


def _infer_supermodel(model_name: str, game: str = 'K1') -> str:
    """
    Infer the correct supermodel for a model name based on KotOR naming conventions.

    K1/K2 body naming:  pf* = female,  pm* = male
    Head  naming:       pfh* = female head,  pmh* = male head
    """
    name_lo = (model_name or '').lower()
    lut = _K2_SUPERMODELS if game == 'K2' else _K1_SUPERMODELS
    if name_lo.startswith('pf'):
        return lut['female']
    if name_lo.startswith('pm'):
        return lut['male']
    return lut['default']


def _validate_supermodel_pair(body_model, head_model, game: str = 'K1') -> list:
    """
    Check that both models have the same supermodel reference.

    Returns a list of warning strings (empty = all good).
    """
    warnings = []
    body_sm = (getattr(body_model, 'supermodel', None) or '').strip().lower()
    head_sm = (getattr(head_model,  'supermodel', None) or '').strip().lower()

    # Filter out null/none/empty
    body_sm_eff = body_sm if body_sm not in ('', 'null', 'none') else None
    head_sm_eff = head_sm if head_sm not in ('', 'null', 'none') else None

    if body_sm_eff and head_sm_eff and body_sm_eff != head_sm_eff:
        warnings.append(
            f"Supermodel mismatch: body='{body_sm_eff}' head='{head_sm_eff}'. "
            f"Both must reference the same supermodel for animations to stay in sync. "
            f"Set both to '{_infer_supermodel(body_model.name, game)}' "
            f"(or whichever rig this character uses)."
        )
    elif not body_sm_eff:
        expected = _infer_supermodel(body_model.name, game)
        warnings.append(
            f"Body model '{body_model.name}' has no supermodel set. "
            f"Expected '{expected}' for {game} — animations may not play."
        )
    elif not head_sm_eff:
        expected = _infer_supermodel(head_model.name, game)
        warnings.append(
            f"Head model '{head_model.name}' has no supermodel set. "
            f"Expected '{expected}' for {game} — animations may not play."
        )
    return warnings


# ─────────────────────────────────────────────────────────────────────────────
#  CreatureAssembly — authentic dual-model engine simulation
# ─────────────────────────────────────────────────────────────────────────────

class CreatureAssembly:
    """
    Authentic KotOR engine simulation: keeps body and head as two separate
    model objects joined at the 'headhook' node — exactly replicating
    Aurora engine's Model::attachModel("headhook", headModel) call.

    This is the correct architecture for GhostRigger's viewport preview and
    for Option B1 export (two separate MDL files).

    Usage (preview)
    ---------------
        assembly = CreatureAssembly.from_models(body_model, head_model, game='K1')
        if assembly.ok:
            # Both models animate independently from the same supermodel
            # The headhook node's world transform parents the head for rendering
            hook_pos = assembly.headhook_world_pos

    Usage (export — Option B1)
    --------------------------
        result = assembly.export_separate()
        # result['body_model'] and result['head_model'] are ready to write as
        # two separate ASCII MDL files, supermodels validated/fixed
    """

    def __init__(self):
        self.body_model = None
        self.head_model = None
        self.game: str = 'K1'
        self.ok: bool = False
        self.message: str = ''
        self.warnings: list = []
        self.headhook_node = None          # node object in body_model
        self.headhook_world_pos = None     # (x,y,z) world-space position
        self._used_fallback_hook: bool = False

    @classmethod
    def from_models(
        cls,
        body_model,
        head_model,
        game: str = 'K1',
    ) -> 'CreatureAssembly':
        """
        Build a CreatureAssembly from two already-loaded KotorModel objects.

        Parameters
        ----------
        body_model : KotorModel  – the body / outfit MDL
        head_model : KotorModel  – the head MDL
        game       : 'K1' or 'K2'

        Returns
        -------
        CreatureAssembly with .ok=True on success
        """
        asm = cls()
        asm.game = game

        if body_model is None:
            asm.message = "No body model supplied."
            return asm
        if head_model is None:
            asm.message = "No head model supplied."
            return asm

        asm.body_model = body_model
        asm.head_model = head_model

        # Locate headhook node in body
        hook_node, used_fallback = _find_headhook_node(body_model, strict=False)
        if hook_node is None:
            asm.message = (
                f"Body model '{body_model.name}' has no 'headhook' node. "
                "KotOR body models always have a dummy node named exactly "
                "'headhook' at the neck socket. Select a different body model "
                "or add a 'headhook' dummy to this model."
            )
            return asm

        asm.headhook_node = hook_node
        asm.headhook_world_pos = _world_pos_of_node(hook_node)
        asm._used_fallback_hook = used_fallback

        # Supermodel validation
        asm.warnings = _validate_supermodel_pair(body_model, head_model, game)
        if used_fallback:
            asm.warnings.insert(0,
                f"Body '{body_model.name}' uses non-standard hook node "
                f"'{hook_node.name}' — real KotOR bodies use 'headhook'."
            )

        asm.ok = True
        asm.message = (
            f"Assembly ready: body='{body_model.name}' + head='{head_model.name}' "
            f"via '{hook_node.name}' @ {asm.headhook_world_pos}  [{game}]"
        )
        log.info("CreatureAssembly.from_models: %s", asm.message)
        if asm.warnings:
            for w in asm.warnings:
                log.warning("CreatureAssembly warning: %s", w)
        return asm

    @classmethod
    def from_resrefs(
        cls,
        body_resref: str,
        head_resref: str,
        resource_manager,
        game: str = 'K1',
    ) -> 'CreatureAssembly':
        """
        Build a CreatureAssembly by loading both models from a ResourceManager.

        Parameters
        ----------
        body_resref       : e.g. 'pmbc1' (male clothing body)
        head_resref       : e.g. 'pmhc1' (male head 1)
        resource_manager  : has get_mdl(resref, game) and get_mdx(resref, game)
        game              : 'K1' or 'K2'

        Returns
        -------
        CreatureAssembly with .ok=True on success
        """
        asm = cls()
        asm.game = game

        def _load(resref):
            try:
                mdl_bytes = resource_manager.get_mdl(resref.lower(), game)
                if mdl_bytes is None:
                    # Try the other game version as fallback
                    other = 'K2' if game == 'K1' else 'K1'
                    mdl_bytes = resource_manager.get_mdl(resref.lower(), other)
                if mdl_bytes is None:
                    return None, f"Model '{resref}' not found in {game} library."
                mdx_bytes = resource_manager.get_mdx(resref.lower(), game) or b''
                from ..game.kotor_loader import load_model_from_bytes
                model = load_model_from_bytes(mdl_bytes, mdx_bytes)
                if model is None:
                    return None, f"Could not parse model '{resref}'."
                return model, None
            except Exception as exc:
                return None, f"Error loading '{resref}': {exc}"

        body_model, err = _load(body_resref)
        if body_model is None:
            asm.message = err or f"Could not load body '{body_resref}'."
            return asm

        head_model, err = _load(head_resref)
        if head_model is None:
            asm.message = err or f"Could not load head '{head_resref}'."
            return asm

        return cls.from_models(body_model, head_model, game=game)

    def export_separate(self) -> dict:
        """
        Option B1 — Export as two separate MDL files, exactly how KotOR stores
        character models.  Validates and (optionally) fixes the supermodel
        references so both models use the same supermodel.

        Returns
        -------
        dict:
            ok           : bool
            body_model   : KotorModel (clone, supermodel fixed if needed)
            head_model   : KotorModel (clone, supermodel fixed if needed)
            body_name    : suggested filename for body (e.g. 'pmbc1')
            head_name    : suggested filename for head  (e.g. 'pmhc1')
            supermodel   : the shared supermodel name applied to both
            warnings     : list[str]  – any issues found (non-fatal)
            message      : str        – human-readable summary
        """
        import copy as _copy

        if not self.ok:
            return {'ok': False, 'body_model': None, 'head_model': None,
                    'body_name': '', 'head_name': '', 'supermodel': '',
                    'warnings': [], 'message': self.message}

        body_out = _copy.deepcopy(self.body_model)
        head_out = _copy.deepcopy(self.head_model)
        warnings = list(self.warnings)

        # Determine the correct shared supermodel
        body_sm = (getattr(body_out, 'supermodel', None) or '').strip().lower()
        head_sm = (getattr(head_out,  'supermodel', None) or '').strip().lower()
        body_sm_eff = body_sm if body_sm not in ('', 'null', 'none') else None
        head_sm_eff = head_sm if head_sm not in ('', 'null', 'none') else None

        # Choose the canonical supermodel to apply to both
        if body_sm_eff and body_sm_eff == head_sm_eff:
            # Both already agree — perfect
            shared_sm = body_sm_eff
        elif body_sm_eff and not head_sm_eff:
            # Body has supermodel, head doesn't — copy body's to head
            shared_sm = body_sm_eff
            head_out.supermodel = shared_sm
            warnings.append(
                f"Head '{head_out.name}' had no supermodel — set to "
                f"'{shared_sm}' (matching body)."
            )
        elif head_sm_eff and not body_sm_eff:
            # Head has supermodel, body doesn't — copy head's to body
            shared_sm = head_sm_eff
            body_out.supermodel = shared_sm
            warnings.append(
                f"Body '{body_out.name}' had no supermodel — set to "
                f"'{shared_sm}' (matching head)."
            )
        elif body_sm_eff and head_sm_eff and body_sm_eff != head_sm_eff:
            # Mismatch — use the inferred canonical supermodel
            shared_sm = _infer_supermodel(body_out.name, self.game)
            body_out.supermodel = shared_sm
            head_out.supermodel = shared_sm
            warnings.append(
                f"Supermodel mismatch fixed: body was '{body_sm_eff}', "
                f"head was '{head_sm_eff}' → both set to '{shared_sm}'."
            )
        else:
            # Neither has one — infer from body name
            shared_sm = _infer_supermodel(body_out.name, self.game)
            body_out.supermodel = shared_sm
            head_out.supermodel = shared_sm
            warnings.append(
                f"No supermodel found on either model — both set to "
                f"'{shared_sm}' (inferred for {self.game})."
            )

        # Verify headhook node is present in body export
        hook, _ = _find_headhook_node(body_out, strict=True)
        if hook is None:
            # Try with fallbacks
            hook, used_fb = _find_headhook_node(body_out, strict=False)
            if hook is not None and used_fb:
                warnings.append(
                    f"Body '{body_out.name}': headhook node is named "
                    f"'{hook.name}' — KotOR expects exactly 'headhook'. "
                    "Rename it before exporting for the game."
                )

        body_name = (body_out.name or 'body').lower()
        head_name = (head_out.name or 'head').lower()

        msg = (
            f"B1 export ready: '{body_name}.mdl' + '{head_name}.mdl'  "
            f"supermodel='{shared_sm}'  [{self.game}]"
        )
        if warnings:
            msg += f"  ({len(warnings)} warning(s))"

        log.info("CreatureAssembly.export_separate: %s", msg)
        return {
            'ok': True,
            'body_model': body_out,
            'head_model': head_out,
            'body_name': body_name,
            'head_name': head_name,
            'supermodel': shared_sm,
            'warnings': warnings,
            'message': msg,
        }

    def get_viewport_preview_model(self):
        """
        Return the body model with the head model attached at the headhook node
        for viewport preview.  This is the snap_head_onto_body merge path —
        produces a single KotorModel where the head's root node is a child of
        the headhook bone.  No vertex movement, no scaling, no anim merging.

        Returns
        -------
        dict  (same schema as snap_head_onto_body return value)
        """
        if not self.ok:
            return {'ok': False, 'model': None, 'message': self.message,
                    'headhook_pos': None, 'warnings': self.warnings}
        return snap_head_onto_body(
            self.body_model,
            self.head_model,
            scale_head=False,       # No scaling — heads are authored at correct scale
            merge_animations=False, # No merging — supermodel handles sync
        )


# ─────────────────────────────────────────────────────────────────────────────
#  snap_head_onto_body  —  corrected viewport-merge implementation
#  (single combined model for the viewport; NOT the export format)
# ─────────────────────────────────────────────────────────────────────────────

def snap_head_onto_body(
    body_model,
    head_model,
    scale_head: bool = False,
    merge_animations: bool = False,
) -> dict:
    """
    Attach a KotOR head model onto a body model for viewport display.

    This replicates Aurora engine's  body->attachModel("headhook", head)  call:
      • The head's root node is attached as a direct child of the 'headhook' bone.
      • No vertices are moved or scaled (heads are already authored at game scale).
      • No animations are merged (both models share the same supermodel).
      • The head's internal hierarchy (skull, jaw, eyeballs) is preserved intact.

    This produces a single KotorModel for the viewport.  For two-file export
    (the authentic game format) use  CreatureAssembly.export_separate()  instead.

    Parameters
    ----------
    body_model       : KotorModel  – body / outfit model (will be cloned)
    head_model       : KotorModel  – head model to attach (will be cloned)
    scale_head       : bool  – legacy option; default False (not authentic)
    merge_animations : bool  – legacy option; default False (not authentic)

    Returns
    -------
    dict:
        ok           : bool
        model        : KotorModel or None  – combined model
        message      : str
        headhook_pos : tuple(x,y,z) or None
        warnings     : list[str]
    """
    import copy as _copy

    if body_model is None:
        return {'ok': False, 'model': None, 'message': "No body model supplied.",
                'headhook_pos': None, 'warnings': []}
    if head_model is None:
        return {'ok': False, 'model': None, 'message': "No head model supplied.",
                'headhook_pos': None, 'warnings': []}

    try:
        combined  = _copy.deepcopy(body_model)
        head_copy = _copy.deepcopy(head_model)

        # ── 1. Find headhook node (strict first, then fallbacks) ─────────────
        hook_node, used_fallback = _find_headhook_node(combined, strict=False)
        if hook_node is None:
            return {
                'ok': False, 'model': None,
                'message': (
                    f"Body model '{body_model.name}' has no 'headhook' node. "
                    "KotOR body models must have a dummy node named 'headhook' "
                    "at the neck socket."
                ),
                'headhook_pos': None,
                'warnings': [],
            }

        hook_world = _world_pos_of_node(hook_node)
        warnings = []
        if used_fallback:
            warnings.append(
                f"Non-standard hook node '{hook_node.name}' used "
                "(real KotOR bodies use 'headhook')."
            )

        # ── 2. Find head model's root node ───────────────────────────────────
        # The head root is the top-level node of the head model's hierarchy.
        # We attach it directly as a child of headhook — preserving the entire
        # head skeleton (jaw, eyeball bones, etc.) intact beneath it.
        head_root = getattr(head_copy, 'root_node', None)
        if head_root is None:
            # Fallback: first node with no parent
            for node in head_copy.all_nodes():
                if getattr(node, 'parent', None) is None:
                    head_root = node
                    break

        if head_root is None:
            return {
                'ok': False, 'model': None,
                'message': f"Head model '{head_model.name}' has no root node.",
                'headhook_pos': hook_world,
                'warnings': warnings,
            }

        # ── 3. Optional legacy scaling (non-authentic; off by default) ───────
        scale_factor = 1.0
        if scale_head:
            try:
                head_copy.compute_bounds()
                combined.compute_bounds()
                body_h = max(0.001,
                    getattr(combined, 'bb_max', (0,0,1.8))[2]
                    - getattr(combined, 'bb_min', (0,0,0.0))[2])
                head_dz = max(0.001,
                    getattr(head_copy, 'bb_max', (0,0,1.0))[2]
                    - getattr(head_copy, 'bb_min', (0,0,0.0))[2])
                scale_factor = max(0.5, min(2.0, (body_h / 7.0) / head_dz))
            except Exception:
                scale_factor = 1.0

        # ── 4. Attach head root as child of headhook ─────────────────────────
        # This is the CORRECT operation: the head's entire subtree (skull, jaw,
        # eyes) becomes a child of the headhook bone.  No vertex manipulation.
        #
        # CRITICAL FIX: Some KotOR NPC head models (e.g. darthband_h, pfh heads)
        # were authored as standalone models and store their root at a large negative
        # Z offset equal to the expected headhook world Z (typically ~ -1.55).
        # This allows them to display correctly when viewed in isolation (Z=0 appears
        # at body-origin height), but when parented to the headhook the negative offset
        # cancels the hook's positive Z, placing the head at world Z≈0 (body level).
        #
        # DETECTION: if |head_root.position.z + hook_world.z| < 0.15, the head root
        # was likely authored with this negative-offset convention.  In that case,
        # zero out the head root's Z offset so parenting to the headhook works correctly.
        # The threshold 0.15 avoids false positives on heads with small intentional offsets.
        if not hasattr(hook_node, 'children') or hook_node.children is None:
            hook_node.children = []
        head_root_pos = getattr(head_root, 'position', (0.0, 0.0, 0.0))
        hook_wz = hook_world[2] if hook_world else 0.0
        # Check if root Z roughly cancels hook Z (the standalone-origin convention)
        _combined_z = hook_wz + head_root_pos[2]
        if abs(_combined_z) < 0.25 and abs(head_root_pos[2]) > 0.5:
            # Head root has large negative Z offset designed to cancel hook Z.
            # Zero it out so the head attaches at the hook's actual height.
            head_root.position = (head_root_pos[0], head_root_pos[1], 0.0)
            warnings.append(
                f"Head root '{head_root.name}' had negative Z offset {head_root_pos[2]:.3f} "
                f"(standalone convention) — corrected to 0 for body attachment."
            )
            log.debug(
                "snap_head_onto_body: corrected head root '%s' Z offset %.3f→0 "
                "(hook_wz=%.3f, combined=%.3f)",
                head_root.name, head_root_pos[2], hook_wz, _combined_z
            )
        head_root.parent = hook_node
        hook_node.children.append(head_root)

        # ── 5. Legacy scaling (vertices only, non-authentic) ─────────────────
        if scale_head and scale_factor != 1.0:
            def _scale_verts(node, s, visited=None):
                if visited is None:
                    visited = set()
                if id(node) in visited:
                    return
                visited.add(id(node))
                if getattr(node, 'is_mesh', False) or getattr(node, 'is_skin', False):
                    verts = getattr(node, 'vertices', None)
                    if verts:
                        # Scale around the hook world position
                        cx, cy, cz = hook_world
                        node.vertices = [
                            ((v[0]-cx)*s+cx, (v[1]-cy)*s+cy, (v[2]-cz)*s+cz)
                            for v in verts
                        ]
                for child in getattr(node, 'children', []):
                    _scale_verts(child, s, visited)
            _scale_verts(head_root, scale_factor)

        # ── 6. Optional legacy animation merge (non-authentic; off by default) 
        if merge_animations:
            try:
                merge_supermodel_animations(combined, head_copy)
            except Exception:
                pass

        combined.compute_bounds()
        log.info(
            "snap_head_onto_body: '%s' head → '%s' body  hook='%s'  scale=%.3f",
            head_model.name, body_model.name, hook_node.name, scale_factor,
        )
        return {
            'ok': True,
            'model': combined,
            'message': (
                f"Head '{head_model.name}' → body '{body_model.name}' "
                f"via '{hook_node.name}'"
                + (f"  scale={scale_factor:.3f}" if scale_head else "")
            ),
            'headhook_pos': hook_world,
            'warnings': warnings,
        }

    except Exception as exc:
        log.error("snap_head_onto_body error: %s", exc, exc_info=True)
        return {
            'ok': False, 'model': None,
            'message': f"Head-snap failed: {exc}",
            'headhook_pos': None,
            'warnings': [],
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Convenience wrapper: assemble_creature()
# ─────────────────────────────────────────────────────────────────────────────

def assemble_creature(
    body_model,
    head_model,
    game: str = 'K1',
    mode: str = 'preview',
) -> dict:
    """
    High-level character-builder entry point.

    Parameters
    ----------
    body_model : KotorModel
    head_model : KotorModel
    game       : 'K1' or 'K2'
    mode       : 'preview'         → single merged model for viewport
                 'export_separate' → Option B1: two separate models (authentic)

    Returns
    -------
    For mode='preview'         → dict from snap_head_onto_body
    For mode='export_separate' → dict from CreatureAssembly.export_separate
    Both dicts always contain 'ok', 'message', 'warnings'.
    """
    asm = CreatureAssembly.from_models(body_model, head_model, game=game)
    if not asm.ok:
        return {'ok': False, 'message': asm.message, 'warnings': asm.warnings}

    if mode == 'export_separate':
        return asm.export_separate()
    else:
        result = asm.get_viewport_preview_model()
        if 'warnings' not in result:
            result['warnings'] = asm.warnings
        else:
            result['warnings'] = asm.warnings + result['warnings']
        return result


def list_head_models(library, game: str = 'K1') -> list:
    """
    Return a list of head model resrefs available in the game library.

    Filters to models whose resref matches KotOR head naming conventions:
      K1: pfhXX (female heads), pmhXX (male heads), n_*head* (NPC heads)
      K2: same prefixes + c_*head* (creature heads)

    Returns a sorted list of resref strings.
    """
    try:
        entries = library.list_models_by_class('character', game=game)
        head_prefixes = ('pfh', 'pmh', 'n_', 'p_')
        head_keywords = ('head', 'fhead', 'fchead')
        result = []
        for entry in entries:
            r = entry.resref.lower()
            is_head = (
                any(r.startswith(pfx) for pfx in head_prefixes)
                and any(kw in r for kw in ('head', 'fhd', 'mhd'))
            ) or any(kw in r for kw in head_keywords)
            if is_head:
                result.append(entry.resref)
        return sorted(set(result))
    except Exception as exc:
        log.debug("list_head_models: %s", exc)
        return []


def list_body_models(library, game: str = 'K1') -> list:
    """
    Return a list of body model resrefs available in the game library.

    Filters to models whose resref matches KotOR body naming conventions:
      K1/K2: pfbXX (female bodies), pmbXX (male bodies), n_*body* (NPC bodies)

    Returns a sorted list of resref strings.
    """
    try:
        entries = library.list_models_by_class('character', game=game)
        body_prefixes = ('pfb', 'pmb', 'pmc', 'pfc')
        body_keywords = ('body', 'bod', '_b_', '_body')
        result = []
        for entry in entries:
            r = entry.resref.lower()
            is_body = (
                any(r.startswith(pfx) for pfx in body_prefixes)
            ) or any(kw in r for kw in body_keywords)
            if is_body:
                result.append(entry.resref)
        return sorted(set(result))
    except Exception as exc:
        log.debug("list_body_models: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
#  Full-Character FBX Export Pipeline
#  Phase 99 — One-shot export: body + head (eyes/teeth/tongue) + all animations
# ─────────────────────────────────────────────────────────────────────────────

def _load_model_from_resource_manager(resref: str, resource_manager) -> Any:
    """
    Load a KotorModel by resref from a ResourceManager.

    Returns the parsed KotorModel on success, or None on failure.
    Used internally by export_full_character_fbx to auto-load the base skeleton.
    """
    if resource_manager is None or not resref or resref.upper() == 'NULL':
        return None
    try:
        # ResourceManager.get() returns bytes or None
        mdl_bytes = resource_manager.get(resref.lower(), 3)   # ResType.MDL = 3
        mdx_bytes = resource_manager.get(resref.lower(), 4)   # ResType.MDX = 4
        if not mdl_bytes:
            return None
        from ..game.kotor_loader import load_model_from_bytes
        return load_model_from_bytes(mdl_bytes, mdx_bytes or b'')
    except Exception as exc:
        log.warning("_load_model_from_resource_manager('%s'): %s", resref, exc)
        return None


def export_full_character_fbx(
    body_model,
    head_model=None,
    fbx_path: str = '',
    base_skeleton_model=None,
    game: str = 'K1',
    tex_cache=None,
    export_rigging: bool = True,
    resource_manager=None,
) -> dict:
    """
    Export a complete KotOR character — body + head (including eyes, teeth,
    tongue) + ALL available animations — as a single FBX file ready for
    Unreal Engine.

    Pipeline
    --------
    1.  Deep-copy body and head models so originals are untouched.
    2.  Auto-load the base skeleton (e.g. S_MALE02 / S_FEMALE02) from the
        resource manager if ``base_skeleton_model`` was not supplied.  The
        base skeleton name is taken from body_model.supermodel.
    3.  Merge supermodel animations (walk, run, attack, talk, etc.) from both
        the head model and the base skeleton into the combined model so every
        clip is embedded as a separate FBX AnimStack / Take entry.
    4.  Merge the base skeleton's bone hierarchy into the combined model so
        the FBX skeleton is complete (some body MDLs omit bones present only
        in the supermodel MDL).
    5.  Attach the head's full node tree under the body's 'headhook' bone,
        preserving skull → jaw → eyeball → teeth → tongue hierarchy.
    6.  Force render=True on all facial geometry nodes (eyes, eyelids, teeth,
        tongue, gums, jaw) — some binary MDLs incorrectly store render=0.
    7.  Export the combined model as FBX ASCII 7.4 via FBXExporter, passing
        base_skeleton_model so synthetic supermodel bone stubs receive correct
        bind-pose world matrices instead of identity transforms.

    Unreal Engine Import Workflow
    -----------------------------
    Import the exported FBX into Unreal Engine 5 with:
      • "Import Animations" checked
      • Skeleton: Create New Skeleton (first character) or Use Existing Skeleton
      • Each KotOR animation clip arrives as a separate AnimSequence asset.

    Eyes / teeth / tongue are guaranteed to be included because:
      • _is_facial_geometry() whitelists them by name prefix AND substring.
      • _is_renderable() bypasses the render=False gate for facial nodes.
      • _is_deformation_helper() never classifies them as helpers.

    Parameters
    ----------
    body_model           : KotorModel — body / outfit MDL (required)
    head_model           : KotorModel — head MDL (optional but strongly recommended)
    fbx_path             : str — output .fbx file path
    base_skeleton_model  : KotorModel or None — the shared supermodel skeleton
                           (e.g. S_MALE02).  When None and resource_manager is
                           supplied, the base skeleton is auto-loaded from
                           body_model.supermodel.
    game                 : 'K1' or 'K2'
    tex_cache            : optional TextureCache — textures saved as TGA alongside FBX
    export_rigging       : bool — also write rigging/ JSON sidecar files (default True)
    resource_manager     : optional ResourceManager — used to auto-load the base
                           skeleton when base_skeleton_model is not supplied.

    Returns
    -------
    dict:
        ok             : bool
        fbx_path       : str
        anim_count     : int  — number of animation clips embedded
        node_count     : int  — total skeleton nodes in combined model
        mesh_count     : int  — renderable mesh nodes exported
        facial_nodes   : list[str] — facial geometry node names found & exported
        base_skeleton  : str  — name of the base skeleton used (or '' if none)
        warnings       : list[str]
        message        : str
    """
    import copy as _copy

    warnings: list = []
    facial_nodes_found: list = []
    base_skel_name: str = ''

    # ── 1. Validate inputs ────────────────────────────────────────────────────
    if body_model is None:
        return {'ok': False, 'fbx_path': fbx_path, 'anim_count': 0,
                'node_count': 0, 'mesh_count': 0, 'facial_nodes': [],
                'base_skeleton': '', 'warnings': [],
                'message': "No body model supplied."}
    if head_model is None:
        # head_model is optional — export body-only with animations if none supplied
        warnings.append("No head model supplied — exporting body geometry only.")

    try:
        # ── 2. Deep-copy so originals are untouched ───────────────────────────
        combined  = _copy.deepcopy(body_model)
        head_copy = _copy.deepcopy(head_model) if head_model is not None else None

        # ── 3. Auto-load base skeleton if not provided ────────────────────────
        #
        # KotOR architecture: animations live in the BASE SKELETON MDL file
        # (e.g. S_MALE02.mdl, S_FEMALE02.mdl).  Character body/head models
        # only store their own accessory nodes; the full ~70-bone skeleton plus
        # ALL animation clips (walk, run, attack, talk, force, etc.) are in the
        # supermodel.  Without importing the supermodel, the FBX will have at
        # best a partial skeleton and ZERO animations.
        #
        # We resolve the supermodel name from body_model.supermodel and load it
        # via the ResourceManager when a base_skeleton_model wasn't supplied.
        if base_skeleton_model is None and resource_manager is not None:
            sm_name = getattr(body_model, 'supermodel', 'NULL') or 'NULL'
            if sm_name.upper() not in ('NULL', '', 'NONE'):
                log.info(
                    "export_full_character_fbx: auto-loading base skeleton '%s'",
                    sm_name)
                base_skeleton_model = _load_model_from_resource_manager(
                    sm_name, resource_manager)
                if base_skeleton_model is not None:
                    base_skel_name = base_skeleton_model.name
                    log.info(
                        "export_full_character_fbx: loaded base skeleton '%s' "
                        "(%d animations, %d nodes)",
                        base_skel_name,
                        len(getattr(base_skeleton_model, 'animations', []) or []),
                        sum(1 for _ in base_skeleton_model.all_nodes()),
                    )
                else:
                    warnings.append(
                        f"Could not load base skeleton '{sm_name}' from resource "
                        "manager — animations may be missing or incomplete.")
            elif sm_name.upper() == 'NULL':
                log.debug(
                    "export_full_character_fbx: body model '%s' has no supermodel "
                    "(supermodel=NULL) — assuming self-contained skeleton",
                    body_model.name)
        elif base_skeleton_model is not None:
            base_skel_name = getattr(base_skeleton_model, 'name', '')

        # ── 4. Merge bone hierarchy from base skeleton ────────────────────────
        #
        # The body model may only contain its own mesh nodes; the full skeleton
        # (all 70+ bones: pelvis, spine, clavicles, arms, legs) lives in the
        # supermodel MDL.  merge_supermodel() injects any missing bones from the
        # base skeleton into the combined model's hierarchy so the FBX exporter
        # can emit a complete skeleton and correct bind-pose matrices.
        if base_skeleton_model is not None:
            try:
                combined = merge_supermodel(combined, base_skeleton_model)
                log.info(
                    "export_full_character_fbx: merged skeleton bones from '%s'",
                    base_skel_name or base_skeleton_model.name)
            except Exception as _merge_exc:
                warnings.append(
                    f"Skeleton merge from '{getattr(base_skeleton_model, 'name', '?')}' "
                    f"failed: {_merge_exc}")
                log.warning(
                    "export_full_character_fbx: merge_supermodel failed: %s",
                    _merge_exc, exc_info=True)

        # ── 5. Inherit ALL supermodel animations into the combined model ──────
        #
        # Priority (highest first):
        #   a) Animations already on body_model (body-specific overrides)
        #   b) Animations from head_model (head-specific: jaw, blink, etc.)
        #   c) Animations from base_skeleton_model (the full game animation set)
        #
        # merge_supermodel_animations() only adds clips NOT already present,
        # so earlier sources win and there is no duplication.

        # Merge head animations (facial: jaw open, blink, eyemove, etc.)
        if head_copy is not None and getattr(head_copy, 'animations', None):
            combined = merge_supermodel_animations(combined, head_copy)
            log.debug(
                "export_full_character_fbx: merged %d head animation(s) from '%s'",
                len(head_copy.animations), head_copy.name)

        # Merge base skeleton animations (the full walk/run/attack/talk set)
        if base_skeleton_model is not None:
            base_anims = getattr(base_skeleton_model, 'animations', None) or []
            if base_anims:
                n_before = len(combined.animations)
                combined = merge_supermodel_animations(combined, base_skeleton_model)
                n_added = len(combined.animations) - n_before
                log.info(
                    "export_full_character_fbx: merged %d base-skeleton animation(s) "
                    "from '%s' (total now: %d)",
                    n_added, base_skel_name or base_skeleton_model.name,
                    len(combined.animations))
                if n_added == 0 and not combined.animations:
                    warnings.append(
                        f"No animations found in base skeleton "
                        f"'{getattr(base_skeleton_model, 'name', '?')}'. "
                        "The exported FBX will have no animation data.")
            else:
                warnings.append(
                    f"Base skeleton '{getattr(base_skeleton_model, 'name', '?')}' "
                    "contains no animations.")
        elif not combined.animations:
            warnings.append(
                "No base skeleton available and body model has no animations. "
                "Export will have no animation data. "
                "Supply a resource_manager or base_skeleton_model to fix this.")

        anim_count = len(combined.animations)

        # ── 6. Attach head onto body at the headhook node ────────────────────
        if head_copy is not None:
            hook_node, used_fallback = _find_headhook_node(combined, strict=False)
            if hook_node is None:
                warnings.append(
                    f"Body model '{body_model.name}' has no headhook node. "
                    "Head geometry will be attached at the model root.")
                # Fall back: attach at root
                hook_node = combined.root_node

            if used_fallback and hook_node is not None:
                warnings.append(
                    f"Non-standard headhook node '{hook_node.name}' used "
                    "(expected 'headhook').")

            head_root = getattr(head_copy, 'root_node', None)
            if head_root is None:
                for n in head_copy.all_nodes():
                    if getattr(n, 'parent', None) is None:
                        head_root = n
                        break

            if head_root is None:
                warnings.append(
                    f"Head model '{head_model.name}' has no root node — "
                    "head geometry omitted from export.")
            elif hook_node is not None:
                if not hasattr(hook_node, 'children') or hook_node.children is None:
                    hook_node.children = []
                head_root.parent = hook_node
                hook_node.children.append(head_root)
                log.info(
                    "export_full_character_fbx: head '%s' attached at '%s'",
                    head_model.name, hook_node.name)

        # ── 7. Audit and force-enable facial geometry nodes ───────────────────
        # Walk the entire combined node tree (body + head subtree) and:
        #  a) record facial geometry nodes (eyes, teeth, tongue) that were found
        #  b) force render=True on any that have render=0 set in the binary MDL
        #     (some NPC head variants incorrectly store render=0 on these nodes)
        try:
            from converters.mesh_converter import OBJExporter, _renderable_mesh_nodes
        except ImportError:
            from src.converters.mesh_converter import OBJExporter, _renderable_mesh_nodes  # type: ignore

        for node in combined.all_nodes():
            if OBJExporter._is_facial_geometry(node):
                if getattr(node, 'vertices', None):
                    facial_nodes_found.append(node.name)
                    # Force render=True so the FBX exporter's _is_renderable()
                    # check does not discard these nodes.
                    if not getattr(node, 'render', True):
                        node.render = True
                        log.debug(
                            "export_full_character_fbx: forced render=True "
                            "on facial node '%s'", node.name)

        if head_copy is not None and not facial_nodes_found:
            warnings.append(
                "No facial geometry nodes found in the head model "
                "(eyes/teeth/tongue). The head MDL may not contain separate "
                "eye/teeth/tongue meshes (they may be baked into the main "
                "face skin mesh), or the node names use an unrecognised pattern.")

        # ── 8. Export combined model as FBX ──────────────────────────────────
        try:
            from converters.mesh_converter import FBXExporter
        except ImportError:
            from src.converters.mesh_converter import FBXExporter  # type: ignore

        exporter = FBXExporter()
        ok = exporter.export(
            combined, fbx_path,
            tex_cache=tex_cache,
            export_rigging=export_rigging,
            base_skeleton_model=base_skeleton_model,
        )

        if not ok:
            return {
                'ok': False, 'fbx_path': fbx_path,
                'anim_count': anim_count,
                'node_count': len(list(combined.all_nodes())),
                'mesh_count': 0,
                'facial_nodes': facial_nodes_found,
                'base_skeleton': base_skel_name,
                'warnings': warnings,
                'message': "FBX export failed (see log for details).",
            }

        # Count what was actually exported
        mesh_nodes = _renderable_mesh_nodes(combined)
        node_count  = len(list(combined.all_nodes()))
        mesh_count  = len(mesh_nodes)

        # ── 9. Export textures as TGA files alongside the FBX ────────────────
        # UE5 automatically picks up textures named <texture_name>.tga if they
        # reside in the same directory as the FBX.  We attempt to write them from
        # the tex_cache (PIL images) or from the resource_manager (raw TPC bytes).
        if tex_cache is not None or resource_manager is not None:
            import os as _os
            fbx_dir = _os.path.dirname(_os.path.abspath(fbx_path))
            _exported_textures: set = set()
            for node in mesh_nodes:
                for tname in [node.texture_clean, getattr(node, 'lightmap', '')]:
                    if not tname or tname.upper() in ('NULL', 'BLACK', ''):
                        continue
                    if tname in _exported_textures:
                        continue
                    _exported_textures.add(tname)
                    tga_path = _os.path.join(fbx_dir, f"{tname}.tga")
                    if _os.path.exists(tga_path):
                        continue  # already present
                    # Try tex_cache first (PIL Image)
                    _written = False
                    if tex_cache is not None:
                        try:
                            img = None
                            if hasattr(tex_cache, 'get'):
                                img = tex_cache.get(tname) or tex_cache.get(tname.lower())
                            elif hasattr(tex_cache, '__getitem__'):
                                try:
                                    img = tex_cache[tname]
                                except (KeyError, TypeError):
                                    pass
                            if img is not None:
                                if hasattr(img, 'save'):
                                    img.save(tga_path)
                                    _written = True
                                    log.debug("export_full_character_fbx: wrote texture %s", tga_path)
                        except Exception as _tex_exc:
                            log.debug("export_full_character_fbx: tex_cache write failed for '%s': %s",
                                      tname, _tex_exc)
                    # Try resource_manager (raw TPC bytes → TGA)
                    if not _written and resource_manager is not None:
                        try:
                            from ..game.kotor_loader import load_tpc_as_pil as _tpc2pil
                            tpc_bytes = None
                            if hasattr(resource_manager, 'get_resource'):
                                tpc_bytes = (resource_manager.get_resource(tname, 'tpc') or
                                             resource_manager.get_resource(tname, 'tga'))
                            if tpc_bytes:
                                img = _tpc2pil(tpc_bytes)
                                if img is not None:
                                    img.save(tga_path)
                                    _written = True
                                    log.debug("export_full_character_fbx: wrote TPC→TGA %s", tga_path)
                        except Exception as _tpc_exc:
                            log.debug("export_full_character_fbx: TPC→TGA failed for '%s': %s",
                                      tname, _tpc_exc)
            if _exported_textures:
                log.info("export_full_character_fbx: attempted texture export for %d textures",
                         len(_exported_textures))

        head_name = getattr(head_model, 'name', 'none') if head_model else 'none'
        msg = (
            f"Full character FBX exported: '{fbx_path}'  "
            f"body='{body_model.name}' + head='{head_name}'  "
            f"base_skeleton='{base_skel_name}'  "
            f"animations={anim_count}  meshes={mesh_count}  "
            f"facial_nodes={facial_nodes_found}"
        )
        if warnings:
            msg += f"  ({len(warnings)} warning(s))"
        log.info("export_full_character_fbx: %s", msg)

        return {
            'ok': True,
            'fbx_path': fbx_path,
            'anim_count': anim_count,
            'node_count': node_count,
            'mesh_count': mesh_count,
            'facial_nodes': facial_nodes_found,
            'base_skeleton': base_skel_name,
            'warnings': warnings,
            'message': msg,
        }

    except Exception as exc:
        log.error("export_full_character_fbx: %s", exc, exc_info=True)
        return {
            'ok': False, 'fbx_path': fbx_path,
            'anim_count': 0, 'node_count': 0, 'mesh_count': 0,
            'facial_nodes': facial_nodes_found,
            'base_skeleton': base_skel_name,
            'warnings': warnings,
            'message': f"Export failed: {exc}",
        }
