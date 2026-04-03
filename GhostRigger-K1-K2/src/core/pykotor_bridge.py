"""
pykotor_bridge.py — Bridge between PyKotor's MDL/TPC/Animation structures
and GhostRigger-K1-K2's internal KotorModel representation.

This module provides:
  - patch_tpc_for_pykotor(data)          : Fix TPC headers with zero data_sz
  - pykotor_tpc_to_pil(data)             : Load TPC bytes → PIL RGBA Image
  - load_model_via_pykotor(mdl_path, ...) : Load MDL file → KotorModel
  - load_model_from_bytes_via_pykotor(...): Load MDL bytes → KotorModel
  - is_pykotor_available()               : Returns True if PyKotor is importable

Correct bone-weight indexing (Phase 14.2 fix):
  MDLSkin.bone_indices[slot] → node_id in all_nodes()
  MDLSkin.vertex_bones[vi].vertex_indices → bonemap slots (as float)
  BoneWeight.bone_index = bonemap slot (matches viewport.py bone_transforms key)
  KotorModel.node.bone_map[slot] = bone node name ('' = unused slot)
"""

import logging
import math
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── Optional PIL ──────────────────────────────────────────────────────────────
_PIL = False
try:
    from PIL import Image
    _PIL = True
except ImportError:
    pass

# ── Optional PyKotor ──────────────────────────────────────────────────────────
_PYKOTOR = False
try:
    import sys as _sys
    _pk_path = '/home/user/webapp/PyKotor/Libraries/PyKotor/src'
    if _pk_path not in _sys.path:
        _sys.path.insert(0, _pk_path)
    from pykotor.resource.formats.mdl.mdl_auto import read_mdl as _pk_read_mdl
    from pykotor.resource.formats.mdl.mdl_data import MDLNodeType as _MDLNodeType
    from pykotor.resource.formats.mdl.mdl_types import MDLControllerType as _MDLCtrlType
    from pykotor.resource.formats.tpc.tpc_auto import read_tpc as _pk_read_tpc
    from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat as _TpcFmt
    _PYKOTOR = True
    log.debug("PyKotor bridge: PyKotor available")
except Exception as _pk_err:
    log.debug(f"PyKotor bridge: PyKotor not available ({_pk_err})")

# ── Internal imports ──────────────────────────────────────────────────────────
from .model_data import (
    Animation, AnimEvent, BoneWeight, GameVersion, KotorModel, ModelNode,
    NodeFlags, VertexSkinData,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Controller type constants (match animation_engine.py values)
# ─────────────────────────────────────────────────────────────────────────────
_CTRL_POSITION    = 8    # MDLControllerType.POSITION
_CTRL_ORIENTATION = 20   # MDLControllerType.ORIENTATION
_CTRL_SCALE       = 36   # MDLControllerType.SCALE
_CTRL_ALPHA       = 132  # MDLControllerType.ALPHA  (was 128 in older versions)
_CTRL_SELFILLUM   = 100  # MDLControllerType.SELFILLUMCOLOR / VERTICALDISPLACEMENT / DRAG

# NodeType → NodeFlags mapping
_NODETYPE_TO_FLAGS: Dict[int, int] = {}
if _PYKOTOR:
    _NODETYPE_TO_FLAGS = {
        int(_MDLNodeType.DUMMY):      int(NodeFlags.HEADER),
        int(_MDLNodeType.TRIMESH):    int(NodeFlags.MESH),
        int(_MDLNodeType.DANGLYMESH): int(NodeFlags.MESH) | int(NodeFlags.DANGLY),
        int(_MDLNodeType.LIGHT):      int(NodeFlags.LIGHT),
        int(_MDLNodeType.EMITTER):    int(NodeFlags.EMITTER),
        int(_MDLNodeType.REFERENCE):  int(NodeFlags.REFERENCE),
        int(_MDLNodeType.AABB):       int(NodeFlags.AABB),
        int(_MDLNodeType.SKIN):       int(NodeFlags.SKIN),
        int(_MDLNodeType.SABER):      int(NodeFlags.SABER),
        int(_MDLNodeType.CAMERA):     int(NodeFlags.HEADER),
        int(_MDLNodeType.PATCH):      int(NodeFlags.MESH),
        int(_MDLNodeType.BINARY):     int(NodeFlags.HEADER),
    }

# ─────────────────────────────────────────────────────────────────────────────
#  TPC helpers
# ─────────────────────────────────────────────────────────────────────────────

def patch_tpc_for_pykotor(data: bytes) -> bytes:
    """Patch TPC header data_sz=0 for stock KotOR DXT textures.

    Stock KotOR DXT1/DXT5 TPC files store data_sz=0 in bytes 0-3 of the header.
    PyKotor requires a valid data_sz to locate the TXI trailer.  This function
    computes the correct value and patches the header if needed.

    Returns the (possibly modified) bytes — a copy is made only when patching.
    """
    if len(data) < 128:
        return data
    data_sz = struct.unpack_from('<I', data, 0)[0]
    if data_sz != 0:
        return data  # already valid

    width  = struct.unpack_from('<H', data, 8)[0]
    height = struct.unpack_from('<H', data, 10)[0]
    enc    = struct.unpack_from('B',  data, 12)[0]
    mips   = struct.unpack_from('B',  data, 13)[0]

    if enc not in (2, 4) or width == 0 or height == 0:
        return data  # uncompressed or invalid — don't patch

    # Compute total compressed size across all mip levels
    total = 0
    w, h = width, height
    for _ in range(max(1, mips)):
        bw = max(1, (w + 3) // 4)
        bh = max(1, (h + 3) // 4)
        block_bytes = 8 if enc == 2 else 16  # DXT1=2, DXT5=4
        total += bw * bh * block_bytes
        w = max(1, w >> 1)
        h = max(1, h >> 1)

    buf = bytearray(data)
    struct.pack_into('<I', buf, 0, total)
    log.debug(f"patch_tpc_for_pykotor: patched data_sz=0 → {total} "
              f"({width}×{height} enc={enc} mips={mips})")
    return bytes(buf)


def _attach_txi_metadata(img: 'Image.Image', tpc_obj, raw_data: bytes) -> None:
    """Attach TXI metadata attributes to a PIL image."""
    txi = ''
    try:
        txi = (tpc_obj.txi or '').strip() if isinstance(getattr(tpc_obj, 'txi', None), str) else ''
    except Exception:
        pass
    img._txi_str  = txi        # type: ignore[attr-defined]
    img._tpc_raw  = raw_data   # type: ignore[attr-defined]
    # alpha_test from TPC header bytes 4-7
    try:
        at = struct.unpack_from('<f', raw_data, 4)[0]
        if 0.0 < at <= 1.0:
            img._txi_alpha_test = at   # type: ignore[attr-defined]
        else:
            img._txi_alpha_test = None  # type: ignore[attr-defined]
    except Exception:
        img._txi_alpha_test = None     # type: ignore[attr-defined]


def pykotor_tpc_to_pil(data: bytes) -> Optional['Image.Image']:
    """Convert KotOR TPC bytes → PIL RGBA Image using PyKotor.

    Handles DXT1/DXT5, uncompressed RGBA/RGB/Grey, V-flip for bottom-up
    uncompressed textures, TXI metadata extraction, and alpha_test.

    Returns None if PyKotor or PIL is unavailable, or the data is invalid.
    Attaches to the returned image:
      ._txi_str        (str)  — TXI metadata string (may be empty)
      ._tpc_raw        (bytes)— original raw TPC data
      ._txi_alpha_test (float|None) — alpha cutoff from header, or None
    """
    if not _PYKOTOR or not _PIL or not data or len(data) < 128:
        return None

    # Patch data_sz=0 for stock KotOR DXT textures
    data = patch_tpc_for_pykotor(data)

    try:
        tpc = _pk_read_tpc(data)
        # Record original format before conversion (needed for V-flip decision)
        orig_fmt = tpc.format()
        is_compressed = orig_fmt in (_TpcFmt.DXT1, _TpcFmt.DXT3, _TpcFmt.DXT5)

        tpc.convert(_TpcFmt.RGBA)
        mip = tpc.get(0, 0)  # first layer, first (largest) mipmap
        img = mip.to_pil_image()
        if img is None:
            raise ValueError("PyKotor returned None image from mip.to_pil_image()")
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # V-flip (UV-convention fix):
        # KotOR MDL UV coordinates use V=0=TOP convention (Direct3D / top-down),
        # NOT the OpenGL V=0=BOTTOM convention.  Our CPU rasterizer applies a
        # render-time V-flip of (1-v)*h, which assumes images are stored BOTTOM-UP.
        # To make that formula correct, ALL textures must be in BOTTOM-UP orientation:
        #   - Uncompressed: already bottom-up (OpenGL convention) → no flip needed.
        #   - DXT1/DXT3/DXT5: stored TOP-DOWN by PyKotor → flip to bottom-up.
        # Without this fix: tail UV V=0.015 → row 504 → pink flesh (wrong).
        # With this fix:    flip → V=0.015 → row 504 → original row 7 → dark brown (correct).
        if is_compressed:
            # DXT textures are top-down from PyKotor: flip to bottom-up
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        # Uncompressed textures are already bottom-up: no flip needed

        _attach_txi_metadata(img, tpc, data)
        return img

    except Exception as e:
        log.debug(f"pykotor_tpc_to_pil failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Model loading
# ─────────────────────────────────────────────────────────────────────────────

def load_model_via_pykotor(
    mdl_path: str,
    mdx_path: str = '',
    game_version: Optional[GameVersion] = None,
) -> Optional[KotorModel]:
    """Load a KotOR MDL file via PyKotor and convert to KotorModel.

    Args:
        mdl_path: Path to the .mdl file.
        mdx_path: Path to the .mdx file (auto-detected if empty).
        game_version: Force K1 or K2; auto-detected from header if None.

    Returns:
        KotorModel on success, None on failure.
    """
    if not _PYKOTOR:
        return None

    try:
        mdl_p = Path(mdl_path)
        if not mdl_p.exists():
            log.error(f"load_model_via_pykotor: file not found: {mdl_path}")
            return None

        # Resolve MDX path
        if mdx_path:
            mdx_p = Path(mdx_path) if Path(mdx_path).exists() else None
        else:
            candidate = mdl_p.with_suffix('.mdx')
            mdx_p = candidate if candidate.exists() else None

        pk_mdl = _pk_read_mdl(mdl_p, source_ext=mdx_p)
        model  = _convert_pkmdl_to_kotormodel(pk_mdl, game_version)
        model.mdl_path = str(mdl_p)
        model.mdx_path = str(mdx_p) if mdx_p else ''
        log.debug(f"load_model_via_pykotor: loaded '{model.name}' "
                  f"({len(model.all_nodes())} nodes, {len(model.animations)} anims)")
        return model

    except Exception as e:
        log.error(f"load_model_via_pykotor: error loading '{mdl_path}': {e}", exc_info=True)
        return None


def load_model_from_bytes_via_pykotor(
    mdl_bytes: bytes,
    mdx_bytes: bytes = b'',
    game_version: Optional[GameVersion] = None,
) -> Optional[KotorModel]:
    """Load a KotOR MDL from bytes via PyKotor and convert to KotorModel.

    This is intended for loading real KotOR MDL files that have been read into
    memory.  It is NOT suitable for synthetic MDLs produced by MDLBinaryWriter
    (which may not match PyKotor's expected binary layout for all node types).

    Args:
        mdl_bytes: Raw .mdl file content.
        mdx_bytes: Raw .mdx file content (empty bytes if unavailable).
        game_version: Force K1 or K2; auto-detected from header if None.

    Returns:
        KotorModel on success, None on failure.
    """
    if not _PYKOTOR:
        return None
    if not mdl_bytes or len(mdl_bytes) < 128:
        return None

    try:
        # PyKotor's read_mdl accepts raw bytes directly (faster than BytesIO)
        pk_mdl = _pk_read_mdl(mdl_bytes, source_ext=mdx_bytes if mdx_bytes else None)
        model  = _convert_pkmdl_to_kotormodel(pk_mdl, game_version)
        log.debug(f"load_model_from_bytes_via_pykotor: loaded '{model.name}' "
                  f"({len(model.all_nodes())} nodes, {len(model.animations)} anims)")
        return model

    except Exception as e:
        log.error(f"load_model_from_bytes_via_pykotor: {e}", exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Internal conversion helpers
# ─────────────────────────────────────────────────────────────────────────────

def _detect_game_version(pk_mdl) -> GameVersion:
    """Infer K1 vs K2 from PyKotor model metadata."""
    try:
        cls = str(getattr(pk_mdl, 'classification', '')).upper()
        # K2-only model types include MINIGAME; most K2 models also appear in K1
        # — use the geometry_type field if available
        geo = getattr(pk_mdl, 'geometry_type', None)
        if geo is not None and int(geo) in (4, 5):
            return GameVersion.K2
    except Exception:
        pass
    return GameVersion.K1


def _convert_pkmdl_to_kotormodel(pk_mdl, game_version: Optional[GameVersion]) -> KotorModel:
    """Convert a PyKotor MDL object into a GhostRigger KotorModel."""
    model = KotorModel()
    model.name        = pk_mdl.name or 'unnamed'
    model.supermodel  = str(getattr(pk_mdl, 'supermodel', 'NULL') or 'NULL')
    model.anim_scale  = float(getattr(pk_mdl, 'animation_scale', 1.0) or 1.0)
    model.game_version = game_version or _detect_game_version(pk_mdl)

    # Classification
    try:
        cls_raw = str(getattr(pk_mdl, 'classification', '') or '')
        model.classification = cls_raw.lower() if cls_raw else 'character'
    except Exception:
        model.classification = 'character'

    # Bounding box
    try:
        bmin = pk_mdl.bmin
        bmax = pk_mdl.bmax
        model.bb_min = (float(bmin.x), float(bmin.y), float(bmin.z))
        model.bb_max = (float(bmax.x), float(bmax.y), float(bmax.z))
        model.radius = float(getattr(pk_mdl, 'radius', 0.0) or 0.0)
    except Exception:
        pass

    # Build node_id → PyKotor node lookup for bone mapping
    pk_nodes_by_id: Dict[int, object] = {}
    try:
        for n in pk_mdl.all_nodes():
            pk_nodes_by_id[int(n.node_id)] = n
    except Exception:
        pass

    # Convert node tree
    try:
        if pk_mdl.root is not None:
            model.root_node = _convert_node_tree(pk_mdl.root, None, pk_nodes_by_id)
    except Exception as e:
        log.error(f"_convert_pkmdl_to_kotormodel: node tree conversion failed: {e}",
                  exc_info=True)
        if model.root_node is None:
            model.root_node = ModelNode(name=model.name or 'root')

    # Build name→node map for animation node lookup
    name_to_node: Dict[str, ModelNode] = {}
    for n in model.all_nodes():
        name_to_node[n.name] = n

    # Convert animations
    try:
        for pk_anim in (pk_mdl.anims or []):
            anim = _convert_animation(pk_anim, name_to_node)
            if anim is not None:
                model.animations.append(anim)
    except Exception as e:
        log.error(f"_convert_pkmdl_to_kotormodel: animation conversion failed: {e}",
                  exc_info=True)

    return model


def _convert_node_tree(
    pk_node,
    parent_gr: Optional[ModelNode],
    pk_nodes_by_id: Dict[int, object],
) -> ModelNode:
    """Recursively convert a PyKotor MDLNode tree to GhostRigger ModelNodes."""
    gr_node = _convert_single_node(pk_node, parent_gr, pk_nodes_by_id)
    for pk_child in (pk_node.children or []):
        try:
            child_gr = _convert_node_tree(pk_child, gr_node, pk_nodes_by_id)
            gr_node.children.append(child_gr)
        except Exception as e:
            log.debug(f"_convert_node_tree: skipping child '{getattr(pk_child, 'name', '?')}': {e}")
    return gr_node


def _convert_single_node(
    pk_node,
    parent_gr: Optional[ModelNode],
    pk_nodes_by_id: Dict[int, object],
) -> ModelNode:
    """Convert a single PyKotor MDLNode → GhostRigger ModelNode."""
    gr = ModelNode()
    gr.name   = pk_node.name or 'node'
    gr.index  = int(pk_node.node_id)
    gr.parent = parent_gr

    # Position
    try:
        pos = pk_node.position
        gr.position = (float(pos.x), float(pos.y), float(pos.z))
    except Exception:
        gr.position = (0.0, 0.0, 0.0)

    # Rotation quaternion
    try:
        ori = pk_node.orientation
        gr.rotation = (float(ori.x), float(ori.y), float(ori.z), float(ori.w))
    except Exception:
        gr.rotation = (0.0, 0.0, 0.0, 1.0)

    # Node flags
    node_type_val = int(getattr(pk_node, 'node_type', 1))
    gr.flags = _NODETYPE_TO_FLAGS.get(node_type_val, int(NodeFlags.HEADER))

    # Base-pose controllers (bind pose)
    try:
        _extract_base_controllers(pk_node, gr)
    except Exception as e:
        log.debug(f"_extract_base_controllers failed for '{gr.name}': {e}")

    # Mesh / skin data
    # For SKIN nodes in PyKotor:
    #   pk_node.mesh  = MDLMesh  — vertex positions, UVs, faces, normals
    #   pk_node.skin  = MDLSkin  — bone data (bonemap, vertex_bones) + texture/material
    # Geometry comes from pk_node.mesh; bone data comes from pk_node.skin.
    # For non-skin mesh nodes: pk_node.mesh is the MDLMesh.
    is_skin_node = (node_type_val == int(_MDLNodeType.SKIN)) if _PYKOTOR else False
    mesh_src = None
    try:
        # Always prefer pk_node.mesh for geometry data (vertices/UVs/faces)
        if pk_node.mesh is not None:
            mesh_src = pk_node.mesh
        elif is_skin_node and pk_node.skin is not None:
            # Fallback: use skin as mesh if mesh is unavailable
            mesh_src = pk_node.skin
    except Exception:
        pass

    # For SKIN nodes: also copy texture/material info from pk_node.skin when available
    if is_skin_node and pk_node.skin is not None and mesh_src is not pk_node.skin:
        try:
            # Overlay texture and material properties from skin onto mesh
            _overlay_skin_texture(pk_node.skin, gr)
        except Exception as e:
            log.debug(f"_overlay_skin_texture failed for '{gr.name}': {e}")

    if mesh_src is not None:
        try:
            _fill_mesh_data(pk_node, mesh_src, gr)
        except Exception as e:
            log.debug(f"_fill_mesh_data failed for '{gr.name}': {e}")

    if is_skin_node and pk_node.skin is not None:
        try:
            _fill_skin_data(pk_node.skin, gr, pk_nodes_by_id)
        except Exception as e:
            log.debug(f"_fill_skin_data failed for '{gr.name}': {e}")

    return gr


def _extract_base_controllers(pk_node, gr: ModelNode) -> None:
    """Copy bind-pose controller data from PyKotor node to GhostRigger node."""
    for ctrl in (getattr(pk_node, 'controllers', None) or []):
        try:
            ctype = int(ctrl.controller_type)
            rows  = ctrl.rows
            if not rows:
                continue
            first_row_data = rows[0].data

            if ctype == _CTRL_POSITION and len(first_row_data) >= 3:
                gr.controllers.append({
                    'type': _CTRL_POSITION,
                    'times': [float(r.time) for r in rows],
                    'values': [[float(v) for v in r.data[:3]] for r in rows],
                })
            elif ctype == _CTRL_ORIENTATION and len(first_row_data) >= 4:
                gr.controllers.append({
                    'type': _CTRL_ORIENTATION,
                    'times': [float(r.time) for r in rows],
                    'values': [[float(v) for v in r.data[:4]] for r in rows],
                })
            elif ctype == _CTRL_SCALE:
                gr.controllers.append({
                    'type': _CTRL_SCALE,
                    'times': [float(r.time) for r in rows],
                    'values': [[float(r.data[0])] for r in rows],
                })
            elif ctype == _CTRL_ALPHA:
                gr.controllers.append({
                    'type': _CTRL_ALPHA,
                    'times': [float(r.time) for r in rows],
                    'values': [[float(r.data[0])] for r in rows],
                })
        except Exception as e:
            log.debug(f"_extract_base_controllers: skipping controller {ctrl}: {e}")


def _overlay_skin_texture(pk_skin, gr: ModelNode) -> None:
    """Copy texture and material properties from MDLSkin to GhostRigger node.

    Called for SKIN nodes where vertex geometry comes from pk_node.mesh but
    texture/material metadata is stored in pk_node.skin (MDLSkin).
    """
    try:
        tex1 = str(getattr(pk_skin, 'texture_1', '') or '').strip()
        tex2 = str(getattr(pk_skin, 'texture_2', '') or '').strip()
        if tex1:
            gr.texture   = tex1
            gr.textures  = [tex1]
            gr.tex_count = 1
        if tex2:
            gr.lightmap  = tex2
            if tex2 not in gr.textures:
                gr.textures.append(tex2)
            gr.tex_count = len(gr.textures)
    except Exception:
        pass
    try:
        diff = getattr(pk_skin, 'diffuse', None)
        if diff is not None:
            gr.diffuse = (float(diff.r), float(diff.g), float(diff.b))
        amb = getattr(pk_skin, 'ambient', None)
        if amb is not None:
            gr.ambient = (float(amb.r), float(amb.g), float(amb.b))
    except Exception:
        pass
    try:
        gr.render        = bool(getattr(pk_skin, 'render', True))
        gr.shadow        = bool(getattr(pk_skin, 'shadow', True))
        gr.beaming       = bool(getattr(pk_skin, 'beaming', False))
        gr.bg_geometry   = bool(getattr(pk_skin, 'background_geometry', False))
        gr.transparency_hint = int(getattr(pk_skin, 'transparency_hint', 0))
    except Exception:
        pass


def _fill_mesh_data(pk_node, mesh_obj, gr: ModelNode) -> None:
    """Fill GhostRigger mesh data from a PyKotor MDLMesh/MDLSkin object."""
    # Texture names
    try:
        tex1 = str(getattr(mesh_obj, 'texture_1', '') or '').strip()
        tex2 = str(getattr(mesh_obj, 'texture_2', '') or '').strip()
        if tex1:
            gr.texture   = tex1
            gr.textures  = [tex1]
            gr.tex_count = 1
        if tex2:
            gr.lightmap  = tex2
            if tex2 not in gr.textures:
                gr.textures.append(tex2)
            gr.tex_count = len(gr.textures)
    except Exception:
        pass

    # Material properties
    try:
        diff = getattr(mesh_obj, 'diffuse', None)
        if diff is not None:
            gr.diffuse = (float(diff.r), float(diff.g), float(diff.b))
        amb = getattr(mesh_obj, 'ambient', None)
        if amb is not None:
            gr.ambient = (float(amb.r), float(amb.g), float(amb.b))
    except Exception:
        pass

    # Render flags
    try:
        gr.render        = bool(getattr(mesh_obj, 'render', True))
        gr.shadow        = bool(getattr(mesh_obj, 'shadow', True))
        gr.beaming       = bool(getattr(mesh_obj, 'beaming', False))
        gr.bg_geometry   = bool(getattr(mesh_obj, 'background_geometry', False))
        gr.transparency_hint = int(getattr(mesh_obj, 'transparency_hint', 0))
    except Exception:
        pass

    # UV animation
    try:
        gr.animate_uv  = bool(getattr(mesh_obj, 'animate_uv', False))
        gr.uv_dir_x    = float(getattr(mesh_obj, 'uv_direction_x', 0.0) or 0.0)
        gr.uv_dir_y    = float(getattr(mesh_obj, 'uv_direction_y', 0.0) or 0.0)
        gr.uv_jitter   = float(getattr(mesh_obj, 'uv_jitter', 0.0) or 0.0)
        gr.uv_jitter_speed = float(getattr(mesh_obj, 'uv_jitter_speed', 0.0) or 0.0)
    except Exception:
        pass

    # Vertex positions
    try:
        vp = mesh_obj.vertex_positions
        gr.vertices = [(float(v.x), float(v.y), float(v.z)) for v in vp]
    except Exception:
        gr.vertices = []

    # Vertex normals
    try:
        vn = mesh_obj.vertex_normals
        gr.normals = [(float(n.x), float(n.y), float(n.z)) for n in (vn or [])]
    except Exception:
        gr.normals = []

    # UV coordinates — primary (vertex_uv)
    try:
        uv_list = list(mesh_obj.vertex_uv or [])
        if not uv_list:
            # Try vertex_uvs (KotOR 2 multi-channel)
            uvs_raw = getattr(mesh_obj, 'vertex_uvs', None) or []
            uv_list = list(uvs_raw[0]) if uvs_raw else []
        gr.uvs = [(float(uv.x), float(uv.y)) for uv in uv_list]
    except Exception:
        gr.uvs = []

    # Secondary (lightmap) UVs — vertex_uv1
    try:
        uv2 = list(getattr(mesh_obj, 'vertex_uv1', None) or [])
        gr.uvs2 = [(float(uv.x), float(uv.y)) for uv in uv2]
    except Exception:
        gr.uvs2 = []

    # Faces + face UVs
    # KotOR MDL faces have t1=t2=t3=-1 for all stock models, meaning UV index
    # equals vertex index.  We store face_uvs as (v1, v2, v3) in that case.
    try:
        face_list = list(mesh_obj.faces or [])
        gr.faces     = []
        gr.face_uvs  = []
        for f in face_list:
            v1, v2, v3 = int(f.v1), int(f.v2), int(f.v3)
            gr.faces.append((v1, v2, v3))
            t1 = int(f.t1) if hasattr(f, 't1') and f.t1 is not None and f.t1 >= 0 else v1
            t2 = int(f.t2) if hasattr(f, 't2') and f.t2 is not None and f.t2 >= 0 else v2
            t3 = int(f.t3) if hasattr(f, 't3') and f.t3 is not None and f.t3 >= 0 else v3
            gr.face_uvs.append((t1, t2, t3))
    except Exception as e:
        log.debug(f"_fill_mesh_data faces error for '{gr.name}': {e}")
        gr.faces    = []
        gr.face_uvs = []

    # Bounding box
    try:
        bb_min = mesh_obj.bb_min
        bb_max = mesh_obj.bb_max
        gr.bb_min = (float(bb_min.x), float(bb_min.y), float(bb_min.z))
        gr.bb_max = (float(bb_max.x), float(bb_max.y), float(bb_max.z))
    except Exception:
        pass


def _fill_skin_data(
    pk_skin,
    gr: ModelNode,
    pk_nodes_by_id: Dict[int, object],
) -> None:
    """Fill GhostRigger skin/bone data from a PyKotor MDLSkin object.

    Bone index mapping (Phase 14.2 fix):
      pk_skin.bone_indices[bonemap_slot] → PyKotor node_id
      pk_skin.vertex_bones[vi].vertex_indices → bonemap_slot (as float)
      BoneWeight.bone_index = bonemap_slot  (key for bone_transforms in viewport.py)
      gr.bone_map[bonemap_slot] = bone node name ('' for unused slots/-1)

    The viewport's _build_bone_transforms() enumerates gr.bone_map with enumerate()
    and keys bone_transforms[slot] = transforms.  _lbs_vertex then accesses
    bone_transforms[bw.bone_index].  So bone_index must be the bonemap slot.
    """
    # Build gr.bone_map: bonemap_slot → bone node name
    raw_bonemap = list(pk_skin.bonemap or [])
    # pk_skin.bone_indices maps bonemap_slot → PyKotor node_id
    raw_bone_indices = list(pk_skin.bone_indices or [])

    gr.bone_map = []
    for slot_idx, node_id in enumerate(raw_bone_indices):
        nid = int(node_id)
        if nid < 0:
            gr.bone_map.append('')
        else:
            pk_n = pk_nodes_by_id.get(nid)
            gr.bone_map.append(pk_n.name if pk_n else '')

    # Pad bone_map to cover all bonemap entries if needed
    while len(gr.bone_map) < len(raw_bonemap):
        gr.bone_map.append('')

    # Build per-vertex skin data
    # vertex_bones[vi].vertex_indices → bonemap slot (as float, -1 = unused)
    # vertex_bones[vi].vertex_weights → weight for that slot
    gr.skin_data = []
    vertex_bones = list(pk_skin.vertex_bones or [])
    for bv in vertex_bones:
        vsd = VertexSkinData()
        vis  = bv.vertex_indices   # tuple of 4 bonemap slots (float)
        wts  = bv.vertex_weights   # tuple of 4 weights
        for i in range(4):
            slot = int(vis[i]) if vis[i] is not None else -1
            w    = float(wts[i]) if wts[i] is not None else 0.0
            if slot < 0 or w <= 1e-6 or not math.isfinite(w):
                continue
            vsd.influences.append(BoneWeight(bone_index=slot, weight=w))
        gr.skin_data.append(vsd)


# ─────────────────────────────────────────────────────────────────────────────
#  Animation conversion
# ─────────────────────────────────────────────────────────────────────────────

def _convert_animation(pk_anim, name_to_node: Dict[str, ModelNode]) -> Optional[Animation]:
    """Convert a PyKotor MDLAnimation → GhostRigger Animation."""
    try:
        anim = Animation()
        anim.name            = pk_anim.name or 'default'
        anim.length          = float(pk_anim.length or pk_anim.anim_length or 0.0)
        anim.transition_time = float(pk_anim.transition_time or pk_anim.transition_length or 0.25)
        # root model name
        try:
            anim.anim_root = str(getattr(pk_anim, 'root_model', '') or '')
        except Exception:
            anim.anim_root = ''

        # Events — PyKotor MDLEvent uses activation_time (not 'time')
        try:
            for evt in (pk_anim.events or []):
                t = float(getattr(evt, 'activation_time', None) or 0.0)
                n = str(getattr(evt, 'name', '') or '')
                anim.events.append(AnimEvent(time=t, name=n))
        except Exception as e:
            log.debug(f"_convert_animation '{anim.name}': event error: {e}")

        # Animation nodes
        try:
            anim_root = getattr(pk_anim, 'root', None)
            if anim_root is not None:
                for pk_anode in _iter_anim_nodes(pk_anim):
                    an = _convert_anim_node(pk_anode)
                    if an is not None:
                        anim.nodes.append(an)
        except Exception as e:
            log.debug(f"_convert_animation '{anim.name}': anim-node error: {e}")

        return anim

    except Exception as e:
        log.error(f"_convert_animation failed: {e}", exc_info=True)
        return None


def _iter_anim_nodes(pk_anim):
    """Yield all nodes in a PyKotor animation via all_nodes() or DFS."""
    try:
        yield from pk_anim.all_nodes()
        return
    except Exception:
        pass
    # Fallback: DFS from root
    root = getattr(pk_anim, 'root', None)
    if root is None:
        return
    stack = [root]
    while stack:
        n = stack.pop()
        yield n
        for c in reversed(list(getattr(n, 'children', []) or [])):
            stack.append(c)


def _convert_anim_node(pk_anode) -> Optional[ModelNode]:
    """Convert a single PyKotor animation node to a GhostRigger ModelNode."""
    try:
        an = ModelNode()
        an.name = pk_anode.name or 'node'
        an.index = int(pk_anode.node_id)

        # Animation controllers
        for ctrl in (getattr(pk_anode, 'controllers', None) or []):
            try:
                ctype = int(ctrl.controller_type)
                rows  = ctrl.rows
                if not rows:
                    continue
                first = rows[0].data
                times  = [float(r.time) for r in rows]
                values = [[float(v) for v in r.data] for r in rows]

                if ctype == _CTRL_POSITION and len(first) >= 3:
                    an.controllers.append({
                        'type': _CTRL_POSITION,
                        'times': times,
                        'values': [v[:3] for v in values],
                    })
                elif ctype == _CTRL_ORIENTATION and len(first) >= 4:
                    an.controllers.append({
                        'type': _CTRL_ORIENTATION,
                        'times': times,
                        'values': [v[:4] for v in values],
                    })
                elif ctype == _CTRL_SCALE:
                    an.controllers.append({
                        'type': _CTRL_SCALE,
                        'times': times,
                        'values': [[v[0]] for v in values],
                    })
                elif ctype == _CTRL_ALPHA:
                    an.controllers.append({
                        'type': _CTRL_ALPHA,
                        'times': times,
                        'values': [[v[0]] for v in values],
                    })
                elif ctype == _CTRL_SELFILLUM and len(first) >= 3:
                    an.controllers.append({
                        'type': _CTRL_SELFILLUM,
                        'times': times,
                        'values': [v[:3] for v in values],
                    })
            except Exception as e:
                log.debug(f"_convert_anim_node '{an.name}': controller error: {e}")

        return an

    except Exception as e:
        log.debug(f"_convert_anim_node failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Public utility
# ─────────────────────────────────────────────────────────────────────────────

def is_pykotor_available() -> bool:
    """Return True if PyKotor was successfully imported."""
    return _PYKOTOR
