"""GhostRigger MCP Debug Materials/Textures/Assembly Bridge — Phase D4+D6.

Expands the MCP debug bridge beyond skinning-only observability.
Provides runtime inspection for:
  - Material/texture bindings per node
  - UV channel assignments (UV0 diffuse, UV1 lightmap)
  - TXI property inspection (clamp, wrap, envmap, alpha_test)
  - Supermodel chain resolution
  - Body-part / submesh listing
  - Missing mesh / texture diagnostics
  - Deformation helper classification audit
  - Render filter results (D6)
  - VBO build status per node (D6)
  - K1 vs K2 model structural differences (D6)

Commands implemented (16 total):
  list_materials, list_textures, get_material_info,
  get_texture_binding_info, get_txi_info, get_uv_channel_info,
  get_supermodel_chain, list_body_parts, get_missing_mesh_report,
  get_node_classification_audit, get_vertex_space_audit,
  get_render_filter_audit, export_render_debug_bundle,
  get_render_filter_results, get_vbo_build_status,
  get_k1_vs_k2_model_differences
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── Ensure project root on path ──────────────────────────────────────────────
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from kotormcp.utils import json_content


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: get loaded model from the debug_skinning session
# ─────────────────────────────────────────────────────────────────────────────

def _get_model():
    """Get the currently loaded model from the debug session."""
    try:
        from kotormcp.tools.debug_skinning import _get_session
        s = _get_session()
        return s.model
    except Exception:
        return None


def _all_mesh_nodes(model):
    """Yield all mesh nodes from the model."""
    if model is None:
        return
    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])
    for n in nodes:
        if getattr(n, 'is_mesh', False):
            yield n


# ─────────────────────────────────────────────────────────────────────────────
#  Data extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_material_info_for_node(node) -> dict:
    """Extract complete material/texture info from a model node."""
    tex = str(getattr(node, 'texture', '') or '').strip()
    lm = str(getattr(node, 'lightmap', '') or '').strip()
    tex_names = list(getattr(node, 'texture_names', []))
    tc = int(getattr(node, 'tex_count', 1))
    has_lm = bool(getattr(node, 'has_lightmap', False))
    diff = getattr(node, 'diffuse', (1.0, 1.0, 1.0))
    amb = getattr(node, 'ambient', (0.2, 0.2, 0.2))

    # TXI properties
    txi_blend = int(getattr(node, 'txi_blending', 0))
    txi_alpha_test = float(getattr(node, 'txi_alpha_test', 0.0))
    txi_env = str(getattr(node, 'txi_envmaptexture', '') or '').strip()
    txi_bumpy = str(getattr(node, 'txi_bumpyshinytexture', '') or '').strip()
    txi_spec = str(getattr(node, 'txi_specularcolour', '') or '').strip()
    txi_clamp_s = bool(getattr(node, 'txi_clamp_s', False))
    txi_clamp_t = bool(getattr(node, 'txi_clamp_t', False))
    txi_decal = bool(getattr(node, 'txi_decal', False))
    txi_wateralpha = float(getattr(node, 'txi_wateralpha', 1.0))
    txi_proc = str(getattr(node, 'txi_proceduretype', '') or '').strip()

    uvs = getattr(node, 'uvs', [])
    uvs_lm = getattr(node, 'uvs_lm', [])
    face_mats = getattr(node, 'face_mats', [])

    # Determine effective lightmap
    effective_lm = has_lm
    if not has_lm and tc == 2 and uvs_lm and face_mats and all(m == 0 for m in face_mats):
        effective_lm = True

    return {
        "name": str(getattr(node, 'name', '?')),
        "texture": tex,
        "lightmap": lm,
        "texture_names": tex_names,
        "tex_count": tc,
        "has_lightmap": has_lm,
        "effective_lightmap": effective_lm,
        "diffuse_color": list(diff[:3]) if diff else [1.0, 1.0, 1.0],
        "ambient_color": list(amb[:3]) if amb else [0.2, 0.2, 0.2],
        "transparency_hint": int(getattr(node, 'transparency_hint', 0)),
        "alpha": float(getattr(node, 'alpha', 1.0)),
        "shininess": float(getattr(node, 'shininess', 0.0)),
        "render": bool(getattr(node, 'render', True)),
        "shadow": bool(getattr(node, 'shadow', False)),
        "is_skin": bool(getattr(node, 'is_skin', False)),
        "is_dangly": bool(getattr(node, 'is_dangly', False)),
        "vertex_count": len(getattr(node, 'vertices', [])),
        "face_count": len(getattr(node, 'faces', [])),
        "uv_count": len(uvs),
        "uv_lm_count": len(uvs_lm),
        "face_mats_unique": sorted(set(face_mats)) if face_mats else [],
        "txi": {
            "blending": txi_blend,
            "alpha_test": txi_alpha_test,
            "envmaptexture": txi_env,
            "bumpyshinytexture": txi_bumpy,
            "specularcolour": txi_spec,
            "clamp_s": txi_clamp_s,
            "clamp_t": txi_clamp_t,
            "decal": txi_decal,
            "wateralpha": txi_wateralpha,
            "proceduretype": txi_proc,
            "numx": int(getattr(node, 'txi_numx', 0)),
            "numy": int(getattr(node, 'txi_numy', 0)),
            "fps": float(getattr(node, 'txi_fps', 0.0)),
        },
    }


def _classify_deform_helper(node, model) -> dict:
    """Classify whether a node is a deformation helper and why."""
    name = str(getattr(node, 'name', '?'))
    name_lower = name.lower()
    is_skin = bool(getattr(node, 'is_skin', False))
    tex = str(getattr(node, 'texture', '') or '').strip().lower()
    has_tex = tex and tex not in ('null', '', 'none', '****')
    uvs = getattr(node, 'uvs', [])
    has_uvs = bool(uvs) and len(uvs) > 0
    verts = getattr(node, 'vertices', [])
    n_verts = len(verts)

    result = {
        "name": name,
        "is_skin": is_skin,
        "texture": tex,
        "has_texture": has_tex,
        "has_uvs": has_uvs,
        "vertex_count": n_verts,
        "classification": "RENDERABLE",
        "reason": "",
    }

    # Model classification
    model_cls = str(getattr(model, 'classification', 'character') or 'character').lower()
    model_type_raw = getattr(model, 'model_type', None)
    model_type = int(model_type_raw) if model_type_raw is not None else 4
    is_module = model_cls in ('effect', 'tile', 'other') or model_type in (0, 2)

    # Inner-geo check
    _INNER_GEO = ('eye', 'lid', 'teeth', 'gum', 'jaw', 'tongue', 'teethu', 'teethl', 'tooth')
    is_inner_geo = any(s in name_lower for s in _INNER_GEO)

    if is_inner_geo and has_tex and has_uvs:
        result["classification"] = "RENDERABLE"
        result["reason"] = "inner-geometry with texture+UVs"
        return result

    # Skin with texture+UVs → always renderable
    if is_skin and has_tex and has_uvs:
        extreme = False
        if uvs:
            try:
                extreme = any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in uvs[:20])
            except Exception:
                pass
        if not extreme:
            result["classification"] = "RENDERABLE"
            result["reason"] = "skin node with texture+valid UVs"
            return result

    # Extreme UV check
    if has_uvs and not is_module:
        try:
            extreme = any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in uvs[:20])
            if extreme:
                result["classification"] = "HELPER"
                result["reason"] = "extreme UV coordinates (|u|>3 or |v|>3)"
                return result
        except Exception:
            pass

    # _g / _dum suffix
    if not is_skin and (name_lower.endswith('_g') or name_lower.endswith('_g0') or name_lower.endswith('_dum')):
        if is_inner_geo and has_tex and has_uvs:
            result["classification"] = "RENDERABLE"
            result["reason"] = "inner-geo _g node with texture+UVs"
            return result
        result["classification"] = "HELPER"
        result["reason"] = f"non-skin node with _g/_dum suffix"
        return result

    # Null texture, non-skin
    if not has_tex and not is_skin:
        if is_module:
            result["classification"] = "RENDERABLE"
            result["reason"] = "module geometry (no texture OK)"
        else:
            result["classification"] = "HELPER"
            result["reason"] = "null texture, non-skin"
        return result

    # Null texture, skin, no UVs
    if not has_tex and is_skin and not has_uvs:
        result["classification"] = "HELPER"
        result["reason"] = "null texture skin with no UVs"
        return result

    # Non-skin, no UVs, non-module
    if not is_skin and not has_uvs and not is_module:
        result["classification"] = "HELPER"
        result["reason"] = "non-skin, no UVs, non-module model"
        return result

    return result


def _get_vertex_space_info(node, model) -> dict:
    """Determine what coordinate space vertices are stored in."""
    import numpy as np

    name = str(getattr(node, 'name', '?'))
    is_skin = bool(getattr(node, 'is_skin', False))
    verts = getattr(node, 'vertices', [])

    if not verts:
        return {"name": name, "space": "EMPTY", "centroid_mag": 0.0}

    v_arr = np.array(verts, dtype=np.float64)
    centroid = v_arr.mean(axis=0)
    centroid_mag = float(np.linalg.norm(centroid))
    bbox_min = v_arr.min(axis=0).tolist()
    bbox_max = v_arr.max(axis=0).tolist()
    extent = (v_arr.max(axis=0) - v_arr.min(axis=0)).tolist()

    supermodel = str(getattr(model, 'supermodel', 'NULL') or 'NULL').strip().upper()

    try:
        from core.model_data import KOTOR_BASE_SKELETONS
        is_base_skel = supermodel in KOTOR_BASE_SKELETONS
    except ImportError:
        is_base_skel = supermodel in ('NULL', '', 'NONE')

    _THRESHOLD = 1.5
    if is_skin and is_base_skel:
        space = "WORLD_SPACE" if centroid_mag > 0.1 else "BONE_LOCAL"
    elif is_skin and not is_base_skel:
        if centroid_mag > _THRESHOLD:
            space = "BAKED_WORLD_OFFSET"
        else:
            space = "BONE_LOCAL"
    else:
        if centroid_mag > _THRESHOLD:
            space = "WORLD_SPACE"
        else:
            space = "LOCAL"

    return {
        "name": name,
        "is_skin": is_skin,
        "space": space,
        "centroid": centroid.tolist(),
        "centroid_mag": round(centroid_mag, 4),
        "bbox_min": [round(x, 4) for x in bbox_min],
        "bbox_max": [round(x, 4) for x in bbox_max],
        "extent": [round(x, 4) for x in extent],
        "supermodel": supermodel,
        "is_base_skeleton": is_base_skel,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  MCP Tool Definitions
# ─────────────────────────────────────────────────────────────────────────────

def get_tools() -> list:
    """Return tool definitions for the MCP tool registry."""
    return TOOL_DEFINITIONS


TOOL_DEFINITIONS = [
    {
        "name": "ghostrigger_list_materials",
        "description": "List all material assignments for the loaded model: texture, lightmap, TXI, per node.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_list_textures",
        "description": "List all unique texture names referenced by the loaded model, with usage counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_material_info",
        "description": "Get detailed material/texture info for a specific node by name.",
        "inputSchema": {
            "type": "object",
            "properties": {"node_name": {"type": "string"}},
            "required": ["node_name"],
        },
    },
    {
        "name": "ghostrigger_get_texture_binding_info",
        "description": "Get texture binding report: which textures are bound to which GL slots for each node.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_txi_info",
        "description": "Get TXI property report for all mesh nodes: wrap mode, blending, envmap, alpha_test.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_uv_channel_info",
        "description": "Get UV channel info: UV0/UV1 counts, lightmap status, face_mats, per-node.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_supermodel_chain",
        "description": "Get supermodel chain: model name, supermodel, classification, whether it's a base skeleton.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_list_body_parts",
        "description": "List all renderable body parts / attached submeshes with vertex counts and textures.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_missing_mesh_report",
        "description": "Diagnose missing/filtered mesh nodes: which nodes are helpers, proxies, or missing.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_node_classification_audit",
        "description": "Full audit of all nodes: deformation helper classification, render/skip decision, reason.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_vertex_space_audit",
        "description": "Audit vertex coordinate space for all mesh nodes: world-space vs bone-local vs baked.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_render_filter_audit",
        "description": "Show exactly which nodes pass/fail each render filter (deform helper, proxy, render flag).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_export_render_debug_bundle",
        "description": "Export a full render debug JSON for the loaded model (materials, UVs, filters, vertex space).",
        "inputSchema": {
            "type": "object",
            "properties": {"output_path": {"type": "string"}},
        },
    },
    # ── Phase D6 regression-debug tools ──────────────────────────────────────
    {
        "name": "ghostrigger_get_render_filter_results",
        "description": (
            "Get the definitive render-filter results for every mesh/skin node: "
            "does each node pass or fail each filter stage (deform-helper, "
            "render flag, has geometry, zero-vertex check)?  Shows per-stage "
            "pass/fail and the final RENDER/SKIP verdict with reason.  "
            "Critical for diagnosing K2 zero-geometry regression."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_vbo_build_status",
        "description": (
            "Get VBO (Vertex Buffer Object) build status for every mesh node: "
            "whether _build_vbo_data would succeed, the stride (floats per "
            "vertex), expected vertex/face/index counts, and failure reasons.  "
            "Useful for diagnosing render failures where geometry exists but "
            "the VBO builder rejects it."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ghostrigger_get_k1_vs_k2_model_differences",
        "description": (
            "Compare structural differences between K1 and K2 model formats "
            "for the loaded model: MDL version, function-pointer fingerprint, "
            "MDX offset handling, skin node vertex recovery status, "
            "classification, header sizes.  Essential for root-cause analysis "
            "of K2-specific regressions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "compare_model_name": {
                    "type": "string",
                    "description": "Optional: name of a second model to compare against (must be loaded separately).",
                },
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
#  Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def handle_list_materials(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    materials = []
    for node in _all_mesh_nodes(model):
        materials.append(_get_material_info_for_node(node))
    return json_content({"model": getattr(model, 'name', '?'), "materials": materials, "count": len(materials)})


async def handle_list_textures(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    tex_usage: Dict[str, Dict] = {}
    for node in _all_mesh_nodes(model):
        n_name = str(getattr(node, 'name', '?'))
        tex = str(getattr(node, 'texture', '') or '').strip().lower()
        if tex and tex not in ('null', '', 'none'):
            tex_usage.setdefault(tex, {"count": 0, "nodes": [], "role": "diffuse"})
            tex_usage[tex]["count"] += 1
            tex_usage[tex]["nodes"].append(n_name)
        lm = str(getattr(node, 'lightmap', '') or '').strip().lower()
        if lm and lm not in ('null', '', 'none'):
            tex_usage.setdefault(lm, {"count": 0, "nodes": [], "role": "lightmap"})
            tex_usage[lm]["count"] += 1
            tex_usage[lm]["nodes"].append(n_name)
        env = str(getattr(node, 'txi_envmaptexture', '') or '').strip().lower()
        if env:
            tex_usage.setdefault(env, {"count": 0, "nodes": [], "role": "envmap"})
            tex_usage[env]["count"] += 1
            tex_usage[env]["nodes"].append(n_name)
    return json_content({"model": getattr(model, 'name', '?'), "textures": tex_usage})


async def handle_get_material_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    target = arguments.get("node_name", "").lower()
    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])
    for node in nodes:
        if str(getattr(node, 'name', '')).lower() == target:
            return json_content(_get_material_info_for_node(node))
    return json_content({"error": f"Node '{target}' not found"})


async def handle_get_texture_binding_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    bindings = []
    for node in _all_mesh_nodes(model):
        info = _get_material_info_for_node(node)
        binding = {
            "name": info["name"],
            "slot0_diffuse": info["texture"],
            "slot1_lightmap": info["lightmap"] if info["effective_lightmap"] else "",
            "slot2_envmap": info["txi"]["envmaptexture"],
            "slot3_specmap": info["txi"]["specularcolour"],
            "tex_count": info["tex_count"],
            "dispatch": "single-tex" if info["tex_count"] <= 1 else (
                "Case A (lightmap)" if info["effective_lightmap"] else "Case B (multi-mat)"
            ),
        }
        bindings.append(binding)
    return json_content({"model": getattr(model, 'name', '?'), "bindings": bindings})


async def handle_get_txi_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    txi_list = []
    for node in _all_mesh_nodes(model):
        info = _get_material_info_for_node(node)
        txi_list.append({"name": info["name"], "texture": info["texture"], **info["txi"]})
    return json_content({"model": getattr(model, 'name', '?'), "txi_properties": txi_list})


async def handle_get_uv_channel_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    channels = []
    for node in _all_mesh_nodes(model):
        info = _get_material_info_for_node(node)
        channels.append({
            "name": info["name"],
            "uv0_count": info["uv_count"],
            "uv1_count": info["uv_lm_count"],
            "tex_count": info["tex_count"],
            "has_lightmap": info["has_lightmap"],
            "effective_lightmap": info["effective_lightmap"],
            "face_mats_unique": info["face_mats_unique"],
            "texture": info["texture"],
            "lightmap": info["lightmap"],
        })
    return json_content({"model": getattr(model, 'name', '?'), "uv_channels": channels})


async def handle_get_supermodel_chain(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    supermodel = str(getattr(model, 'supermodel', 'NULL') or 'NULL')
    cls = str(getattr(model, 'classification', 'character') or 'character')
    model_type = getattr(model, 'model_type', None)

    try:
        from core.model_data import KOTOR_BASE_SKELETONS
        is_base = supermodel.strip().upper() in KOTOR_BASE_SKELETONS
    except ImportError:
        is_base = supermodel.strip().upper() in ('NULL', '', 'NONE')

    return json_content({
        "model_name": getattr(model, 'name', '?'),
        "supermodel": supermodel,
        "classification": cls,
        "model_type": int(model_type) if model_type is not None else None,
        "is_base_skeleton": is_base,
        "is_standalone": supermodel.upper() in ('NULL', '', 'NONE'),
    })


async def handle_list_body_parts(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    parts = []
    for node in _all_mesh_nodes(model):
        cls = _classify_deform_helper(node, model)
        if cls["classification"] == "RENDERABLE":
            parts.append({
                "name": cls["name"],
                "is_skin": cls["is_skin"],
                "texture": cls["texture"],
                "vertex_count": cls["vertex_count"],
                "face_count": len(getattr(node, 'faces', [])),
                "render_reason": cls["reason"],
            })
    return json_content({
        "model": getattr(model, 'name', '?'),
        "body_parts": parts,
        "total_renderable": len(parts),
    })


async def handle_get_missing_mesh_report(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    filtered = []
    renderable = []
    for node in _all_mesh_nodes(model):
        cls = _classify_deform_helper(node, model)
        if cls["classification"] == "HELPER":
            filtered.append({"name": cls["name"], "reason": cls["reason"],
                           "is_skin": cls["is_skin"], "texture": cls["texture"],
                           "vertex_count": cls["vertex_count"]})
        else:
            renderable.append(cls["name"])
    return json_content({
        "model": getattr(model, 'name', '?'),
        "filtered_nodes": filtered,
        "renderable_nodes": renderable,
        "filtered_count": len(filtered),
        "renderable_count": len(renderable),
    })


async def handle_get_node_classification_audit(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    audit = []
    for node in _all_mesh_nodes(model):
        cls = _classify_deform_helper(node, model)
        audit.append(cls)
    return json_content({"model": getattr(model, 'name', '?'), "audit": audit})


async def handle_get_vertex_space_audit(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    audit = []
    for node in _all_mesh_nodes(model):
        try:
            info = _get_vertex_space_info(node, model)
            audit.append(info)
        except Exception as e:
            audit.append({"name": str(getattr(node, 'name', '?')), "error": str(e)})
    return json_content({"model": getattr(model, 'name', '?'), "vertex_space_audit": audit})


async def handle_get_render_filter_audit(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    audit = []
    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])
    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        name = str(getattr(node, 'name', '?'))
        verts = getattr(node, 'vertices', [])
        faces = getattr(node, 'faces', [])
        render_flag = bool(getattr(node, 'render', True))
        cls = _classify_deform_helper(node, model)
        passed = (render_flag and len(verts) > 0 and len(faces) > 0
                  and cls["classification"] == "RENDERABLE")
        audit.append({
            "name": name,
            "render_flag": render_flag,
            "has_verts": len(verts) > 0,
            "has_faces": len(faces) > 0,
            "deform_helper": cls["classification"] == "HELPER",
            "helper_reason": cls["reason"] if cls["classification"] == "HELPER" else "",
            "final_verdict": "RENDER" if passed else "SKIP",
        })
    return json_content({"model": getattr(model, 'name', '?'), "render_filter_audit": audit})


async def handle_export_render_debug_bundle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})
    output_path = arguments.get("output_path", "render_debug_bundle.json")

    bundle = {
        "model_name": getattr(model, 'name', '?'),
        "supermodel": str(getattr(model, 'supermodel', 'NULL') or 'NULL'),
        "classification": str(getattr(model, 'classification', 'character') or 'character'),
        "materials": [],
        "vertex_space": [],
        "render_filter": [],
    }

    for node in _all_mesh_nodes(model):
        bundle["materials"].append(_get_material_info_for_node(node))
        try:
            bundle["vertex_space"].append(_get_vertex_space_info(node, model))
        except Exception:
            pass
        bundle["render_filter"].append(_classify_deform_helper(node, model))

    try:
        with open(output_path, 'w') as f:
            json.dump(bundle, f, indent=2, default=str)
        return json_content({"status": "ok", "path": output_path, "node_count": len(bundle["materials"])})
    except Exception as e:
        return json_content({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
#  Phase D6 — K2 Zero-Geometry Regression Debug Tools
# ─────────────────────────────────────────────────────────────────────────────

async def handle_get_render_filter_results(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Definitive render-filter results for every mesh/skin node.

    For each node, reports pass/fail on five filter stages:
      1. render_flag   — MDL author's render=True/False
      2. has_vertices  — len(vertices) > 0
      3. has_faces     — len(faces) > 0
      4. deform_helper — _is_deformation_helper classification
      5. zero_geometry — all vertices are exactly (0,0,0)
    Plus the final RENDER/SKIP verdict.
    """
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})

    game_version = str(getattr(model, 'game_version', 'K1'))
    results = []
    total_render = 0
    total_skip = 0

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    for node in nodes:
        if not getattr(node, 'is_mesh', False) and not getattr(node, 'is_skin', False):
            continue

        name = str(getattr(node, 'name', '?'))
        verts = getattr(node, 'vertices', [])
        faces = getattr(node, 'faces', [])
        render_flag = bool(getattr(node, 'render', True))
        is_skin = bool(getattr(node, 'is_skin', False))

        # Stage 1: render flag
        s1_pass = render_flag

        # Stage 2: has vertices
        s2_pass = len(verts) > 0

        # Stage 3: has faces
        s3_pass = len(faces) > 0

        # Stage 4: deformation helper check
        cls = _classify_deform_helper(node, model)
        s4_pass = cls["classification"] != "HELPER"

        # Stage 5: zero-geometry (all verts at origin)
        all_zero = False
        if verts:
            try:
                all_zero = all(
                    abs(x) < 1e-9 and abs(y) < 1e-9 and abs(z) < 1e-9
                    for x, y, z in verts
                )
            except Exception:
                pass
        s5_pass = not all_zero

        final = "RENDER" if (s1_pass and s2_pass and s3_pass and s4_pass and s5_pass) else "SKIP"
        skip_reasons = []
        if not s1_pass:
            skip_reasons.append("render=False")
        if not s2_pass:
            skip_reasons.append("zero vertices")
        if not s3_pass:
            skip_reasons.append("zero faces")
        if not s4_pass:
            skip_reasons.append(f"deform helper: {cls['reason']}")
        if not s5_pass:
            skip_reasons.append("all vertices at origin")

        if final == "RENDER":
            total_render += 1
        else:
            total_skip += 1

        results.append({
            "name": name,
            "is_skin": is_skin,
            "vertex_count": len(verts),
            "face_count": len(faces),
            "stages": {
                "1_render_flag": s1_pass,
                "2_has_vertices": s2_pass,
                "3_has_faces": s3_pass,
                "4_not_deform_helper": s4_pass,
                "5_not_all_zero": s5_pass,
            },
            "verdict": final,
            "skip_reasons": skip_reasons,
        })

    return json_content({
        "model": getattr(model, 'name', '?'),
        "game_version": game_version,
        "filter_results": results,
        "summary": {
            "total_mesh_nodes": len(results),
            "render": total_render,
            "skip": total_skip,
        },
    })


async def handle_get_vbo_build_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """VBO build status for every mesh node — whether GPU upload would succeed."""
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})

    # Current VBO stride (22 floats: 3+3+2+2+4+4+4)
    VBO_STRIDE = 22

    results = []
    total_ok = 0
    total_fail = 0

    for node in _all_mesh_nodes(model):
        name = str(getattr(node, 'name', '?'))
        verts = getattr(node, 'vertices', [])
        norms = getattr(node, 'normals', [])
        uvs = getattr(node, 'uvs', [])
        uvs_lm = getattr(node, 'uvs_lm', [])
        faces = getattr(node, 'faces', [])
        is_skin = bool(getattr(node, 'is_skin', False))
        skin_data = getattr(node, 'skin_data', [])

        n_verts = len(verts)
        n_faces = len(faces)
        issues = []

        if n_verts == 0:
            issues.append("zero vertices")
        if n_faces == 0:
            issues.append("zero faces")
        if n_verts > 0 and len(norms) == 0:
            issues.append("no normals (will use default)")
        if n_verts > 0 and len(uvs) == 0:
            issues.append("no UVs (will use zeros)")
        if is_skin and len(skin_data) == 0:
            issues.append("skin node but no skin_data")
        if is_skin and len(skin_data) > 0 and len(skin_data) != n_verts:
            issues.append(f"skin_data count ({len(skin_data)}) != vertex count ({n_verts})")

        # Check for degenerate faces (indices out of range)
        bad_faces = 0
        for f in faces:
            if any(idx >= n_verts or idx < 0 for idx in f[:3]):
                bad_faces += 1
        if bad_faces > 0:
            issues.append(f"{bad_faces} faces with out-of-range indices")

        would_succeed = n_verts > 0 and n_faces > 0 and bad_faces == 0
        if would_succeed:
            total_ok += 1
        else:
            total_fail += 1

        results.append({
            "name": name,
            "is_skin": is_skin,
            "vertex_count": n_verts,
            "face_count": n_faces,
            "normal_count": len(norms),
            "uv_count": len(uvs),
            "uv_lm_count": len(uvs_lm),
            "skin_data_count": len(skin_data),
            "vbo_stride": VBO_STRIDE,
            "expected_vbo_floats": n_verts * VBO_STRIDE,
            "expected_index_count": n_faces * 3,
            "would_succeed": would_succeed,
            "issues": issues,
        })

    return json_content({
        "model": getattr(model, 'name', '?'),
        "vbo_build_status": results,
        "summary": {
            "total_nodes": len(results),
            "build_ok": total_ok,
            "build_fail": total_fail,
            "vbo_stride_floats": VBO_STRIDE,
        },
    })


async def handle_get_k1_vs_k2_model_differences(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Compare K1 vs K2 structural differences for the loaded model."""
    model = _get_model()
    if model is None:
        return json_content({"error": "No model loaded"})

    import struct as _struct

    game_version = str(getattr(model, 'game_version', 'K1'))
    name = str(getattr(model, 'name', '?'))
    classification = str(getattr(model, 'classification', 'character'))
    model_type = getattr(model, 'model_type', None)
    supermodel = str(getattr(model, 'supermodel', 'NULL'))

    # Gather node statistics
    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    total_nodes = len(nodes)
    mesh_nodes = [n for n in nodes if getattr(n, 'is_mesh', False)]
    skin_nodes = [n for n in nodes if getattr(n, 'is_skin', False)]
    dummy_nodes = [n for n in nodes if getattr(n, 'is_dummy', False)]

    total_verts = sum(len(getattr(n, 'vertices', [])) for n in mesh_nodes)
    total_faces = sum(len(getattr(n, 'faces', [])) for n in mesh_nodes)
    total_anims = len(getattr(model, 'animations', []))

    # Skin node analysis: check for zero-vertex skin nodes (K2 regression symptom)
    zero_vert_skins = []
    recovered_skins = []
    for n in skin_nodes:
        v = len(getattr(n, 'vertices', []))
        f = len(getattr(n, 'faces', []))
        sd = len(getattr(n, 'skin_data', []))
        entry = {
            "name": str(getattr(n, 'name', '?')),
            "vertices": v, "faces": f, "skin_data_count": sd,
            "texture": str(getattr(n, 'texture', '') or ''),
        }
        if v == 0 and f > 0:
            zero_vert_skins.append(entry)
        elif v > 0 and f > 0:
            recovered_skins.append(entry)

    # K2-specific: check for MDX offset=0 recovery
    # The PyKotor MDX offset=0 bug affects K2 models where the first skin's
    # MDX data starts at byte 0 of the MDX file.  After our fix, those nodes
    # should have vertices recovered.
    mdx_recovery_status = "not_applicable"
    if game_version == 'GameVersion.K2' or 'K2' in game_version:
        if zero_vert_skins:
            mdx_recovery_status = "STILL_BROKEN"
        elif recovered_skins:
            mdx_recovery_status = "RECOVERED"
        else:
            mdx_recovery_status = "no_skins"
    elif game_version == 'GameVersion.K1' or 'K1' in game_version:
        mdx_recovery_status = "not_applicable_k1"

    # K1 vs K2 format differences (reference)
    format_diff = {
        "trimesh_header_size": {"K1": 332, "K2": 340},
        "mdx_resource_type": {"K1": 3008, "K2": 3008},
        "fp1_ranges": {
            "K1_PC": [4273776, 4273392],
            "K2_PC": [4285200, 4284816],
            "Xbox": [4254992, 4285872],
        },
        "k2_extra_fields": ["dirt_enabled", "dirt_texture", "dirt_coordinate_space",
                            "hologram", "hologram_color"],
        "mdx_offset_zero_bug": {
            "description": "PyKotor rejects mdx_data_offset=0 as invalid; offset 0 means start of MDX buffer (valid)",
            "affects": "K2 models where first skin mesh MDX data starts at byte 0",
            "fix": "Patched condition from 'not in (0, 0xFFFFFFFF)' to '!= 0xFFFFFFFF'",
            "recovery": mdx_recovery_status,
        },
    }

    return json_content({
        "model_name": name,
        "game_version": game_version,
        "classification": classification,
        "model_type": int(model_type) if model_type is not None else None,
        "supermodel": supermodel,
        "node_counts": {
            "total": total_nodes,
            "mesh": len(mesh_nodes),
            "skin": len(skin_nodes),
            "dummy": len(dummy_nodes),
        },
        "geometry": {
            "total_vertices": total_verts,
            "total_faces": total_faces,
            "total_animations": total_anims,
        },
        "k2_regression_check": {
            "zero_vertex_skins": zero_vert_skins,
            "recovered_skins": recovered_skins,
            "mdx_recovery_status": mdx_recovery_status,
        },
        "k1_vs_k2_format_differences": format_diff,
    })
