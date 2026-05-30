"""
gpu_renderer.py  –  GhostRigger-K1-K2  GPU fast-path renderer
==============================================================
ModernGL/EGL GPU renderer for the Qt viewport.

Architecture
------------
GpuRenderer.render(model, camera, W, H) → PIL Image (RGBA)

GPU fast-path  (requires moderngl + EGL)
  • Uploads all mesh vertex/UV data as interleaved VBOs (float32)
  • One draw-call per material zone (tex + lightmap + blend-mode)
  • Textures cached as GL Texture2D objects (RGBA8, mipmapped)
  • Supports:
      – Diffuse UV mapping (UV0) with GL_REPEAT wrapping
      – Lightmap compositing (UV1, overbright ×2 multiply pass)
      – TXI additive blending (GL_ONE + GL_ONE)
      – TXI punch-through alpha (alpha-test discard at threshold)
      – TXI environment map (unit 2): KotOR BlendedOver — env additive on
          top of diffuse, weighted by (1 - diffuse.alpha). Both envmaptexture
          and bumpyshinytexture TXI keywords map to this env-map slot.
      – TXI specularcolour map (unit 3, Phase 3.8): per-texel gloss mask
          modulates Phong specular highlight intensity per fragment.
      – RotateTexture (UV swap in vertex shader)
      – UV scroll / animate_uv (uniform offset per draw)
      – Self-illumination colour additive term in fragment shader
      – Animated alpha (uniform)
      – Per-node diffuse colour + Phong lighting (key + fill + ambient)
      – Per-node shininess from ModelNode.shininess (Phase 3.8)

Key rendering correctness fixes (Phase 1)
  BUG-UV:   UV V-axis flipped  → v_uv.y = 1.0 - in_uv.y  in vertex shader
             KotOR MDX stores V=0 at top (D3D convention); OpenGL wants V=0 at bottom.
  BUG-WIND: KotOR uses clockwise triangle winding; set ctx.front_face = 'cw'.
  BUG-ALPHA: Transparent surfaces sorted back-to-front by camera depth before draw.
  BUG-ENVMAP: TXI envmaptexture/bumpyshinytexture → KotOR uses "BlendedOver"
              rendering (xoreos EnvironmentBlendedOver / KotOR.js ADD blend):
              env map is additive on top of diffuse, weighted by (1 - diffuse.alpha).
              'bumpyshinytexture' is an ALIAS for 'envmaptexture' (both KotOR.js
              and xoreos route both keywords to the same env-map texture slot).
  BUG-PUNCH: txi_blending=2 (punchthrough) now correctly sets u_blend_mode=2.

Phase 2 rendering correctness fixes
  FIX-DEFORM:   Deformation-helper mesh nodes (bone proxies with _g suffix, no UVs)
                are now filtered in the GPU path using the same
                _is_deformation_helper logic as the CPU viewport.  This eliminates
                opaque bone-blob ghosts on character models.
                Reference: KotOR engine ProcessSkinSeams() + viewport._is_deformation_helper.
  FIX-ENVFB:    When txi_envmaptexture is set but the env texture is not in the texture
                dict, bind a neutral grey 1×1 fallback instead of nothing.  This keeps
                the surface visible (correct) rather than fully transparent.
                The grey env contributes (1-diffuse.alpha)×grey to lit_color.
                Without this fix, metallic surfaces with transparent diffuse would
                disappear entirely instead of showing the reflection.
  FIX-SEAM:     Skin UV seam expansion: KotOR binary MDL uses per-face tvert (texture-
                vertex) indices that differ from geometry vertex indices (the NWN
                exporter's ProcessSkinSeams duplicates seam verts).  _build_vbo_data
                now always expands to a triangle-list (no IBO) when face_uvs is present
                OR when the node is a skin mesh, correctly assigning per-face UV coords
                to each triangle vertex.
                Reference: PyKotor io_mdl.py ProcessSkinSeams engine note + read_mdl.py.
  FIX-SEAMUV:   Seam-vertex UVs are preserved as authored. KotOR uses GL_REPEAT
                by default, so large finite UV coordinates are valid tiling data.
  FIX-KILL-FACEMATS (Phase D10): REMOVED per-face-material texture splitting.
                face_mats[] is a walk-mesh surface indicator, NOT a texture selector.
                The correct KotOR texture model is: one diffuse on UV0, optional one
                lightmap on UV1, composited as diffuse * lightmap * overbright.
                No per-face texture splitting.  Reference: xoreos, KotOR.js, KotorBlender.
  FIX-FLIPBOOK: TXI proceduretype=cycle nodes (animated sprite sheets: water, displays,
                fire) now advance the frame via anim_time × txi_fps and pass a UV tile
                offset uniform (u_flipbook_offset) to the vertex shader.
                Reference: KotOR TXI spec proceduretype/numx/numy/fps.
  FIX-PERSCACHE: Per-model persistent world-transform cache survives across frames;
                invalidated on model change.  Reduces O(N×depth) per-frame cost to
                O(1) cache lookup for static geometry.

Vertex-space contract (Phase D20-M — SUPERSEDES the old BUG-SKIN note)
  Every node carries a ``vertex_space`` enum set at load time by
  ``src/core/vertex_space.compute_vertex_space()``.  ``_build_vbo_data`` reads
  that field and nothing else to decide whether to transform vertices:

      NODE_LOCAL (0): vertices are node-local; apply full parent-chain
                      world_transform (rotate + translate).  This is the
                      DEFAULT for every KotOR MDL node — including SKIN,
                      DANGLY, and SABER.  Skin meshes are node-local per
                      xoreos ``model_kotor.cpp`` readSkin() and KotOR.js
                      ``OdysseyModelNodeMesh.ts``.  The pre-D20-M claim
                      that skin vertices were "already in world-space and
                      baked by the NWN exporter" was WRONG — it was a
                      coincidence on models whose skin parent chain happened
                      to resolve to identity.
      WORLD (1):      vertices already in model-root space (only set for
                      externally-imported OBJ/FBX); skip world_transform.
                      Not produced by any KotOR MDL loader path.
      AABB_WALK (2):  walkmesh / collision — never rendered.

  See ``_build_vbo_data`` (the ``_node_vs`` switch) and ``src/core/vertex_space.py``
  for the authoritative implementation.  Do NOT reintroduce centroid-magnitude
  or name-based heuristics to decide vertex space — the enum is the contract.

Phase 3.8 rendering correctness fixes (deep audit vs Kotor.NET / KotOR.js / xoreos)
  FIX-ENVBLEND:  CRITICAL: The environment-map blend weight was inverted.
                 Old (wrong): env_weight = diffuse.a   → env replaces opaque areas
                 New (correct): env_weight = 1.0 - diffuse.a  → env shows through
                 transparent areas (matching xoreos renderGeometryEnvMappedOver and
                 KotOR.js ShaderOdysseyModel (1.0 - diffuseColor.a) comment).
                 Source: xoreos GL blend (GL_ONE_MINUS_DST_ALPHA, GL_ONE) for env pass.
  FIX-BUMPYSHINY: 'bumpyshinytexture' TXI command correctly maps to envmaptexture
                 (NOT specbumpmap). Both KotOR.js TXI.ts:161-164 and xoreos
                 modelnode.cpp:479-482 route it to the same env-map texture slot.
  FIX-WATERALPHA: TXI 'wateralpha' parameter now wired to u_wateralpha uniform,
                 modulating final surface transparency for water/lava/glass surfaces.
  FIX-DECAL:    TXI 'decal' flag now wired to u_decal uniform; decal surfaces use
                diffuse alpha as opacity blend weight (compositing over background).
  FIX-TXIFIELDS: ModelNode gains txi_decal, txi_isbumpmap, txi_islightmap fields;
                 _apply_txi_to_node() applies all three from TXI metadata.
  FIX-ENVOPAQUE: After env-map blend, diffuse.a is set to 1.0 — prevents the already-
                 consumed alpha from accidentally making env-map surfaces transparent.
  FIX-LMSHADE:  For module/area geometry with baked lightmaps, skip the Phong
                 directional lighting pass entirely.  The lightmap IS the lighting
                 — applying Phong shade on top double-darkens the scene because
                 lightmaps have a mean intensity of ~0.25 (×2 overbright → ~0.5)
                 and the Phong shade multiplier (~0.65) further reduces to ~0.35.
                 New formula: lit_color = diffuse_tex * lightmap * 2.0  (no Phong).
                 Character models with lightmaps (rare) still use Phong + lightmap.
                 Source: KotOR.js ShaderOdysseyModel.ts USE_LIGHTMAP path (lines
                 359-365): completely replaces directDiffuse with lightmap-only
                 indirectDiffuse, omitting the Phong direct lighting component.

Phase 3.8 new features
  FIX-SPECMAP:  TXI 'specularcolour' texture is now bound to sampler unit 3 and
                modulates the Phong specular highlight per-texel.  Armour/metal
                surfaces with a specular map get per-pixel gloss rather than the
                flat global u_specular float.  When no specular map is present the
                shader falls back to the unchanged global u_specular scalar.
                Sources: Kotor.NET KotorModelLoader.cs specular texture slot;
                KotOR.js ShaderOdysseyModel.ts specularColor uniform;
                xoreos modelnode.cpp _specularColour usage.
  FIX-SHININESS: ModelNode.shininess (parsed from ASCII 'shininess' command or
                binary TrimeshHeader) now drives u_shininess per node instead of
                the global default 20.0.  Zero shininess → no specular highlight.
  FIX-MULTILAYER: build_creature_model() now accepts an optional 'accessory_resrefs'
                list; each accessory MDL is loaded and attached as an overlay model
                by merging its non-skin geometry nodes into a combined scene list.
                This enables cloak/robe/headgear layering over the base body model.
                Sources: KotOR.js OdysseyModel3D.ts:780–803 supermodel stacking;
                Kotor.NET CompositeModel multi-mesh logic.

CPU graphics rendering
  • Disabled. The Qt viewport and renderer failure paths do not rasterize on CPU.

Performance notes
  – GPU path: ~1 ms/frame for typical 10 k-tri KotOR models
  – CPU path: ~300 ms/frame for same (PIL AFFINE per triangle)
  – The GPU path is ~300× faster for fully textured rendering.

Triangle throughput benchmark is included at the bottom of this file
(run directly: python -m src.gui.rendering.gpu_renderer benchmark).

References
----------
  KotOR MDL mesh header: GhostRigger mdl_parser.py + KotorBlender reader.py
  TXI blend modes: KotOR.js / NWN TXI specification
  Lightmap compositing: final = diffuse * lightmap * 2 (overbright multiply)
  Environment map blending: OldRepublicDevs/PyKotor tools/creature.py + TXI spec
  KotorBlender reader.py (OldRepublicDevs fork, Mar 2026): canonical MDL reference
  ModernGL docs: https://moderngl.readthedocs.io/
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import struct
import time
from typing import Dict, List, Optional, Tuple

from src.gui.lighting.light_gizmo_renderer import (
    LIGHT_HELPER_AREA_SIZE,
    LIGHT_HELPER_COLORS,
    LIGHT_HELPER_DIRECTION_LENGTH,
    LIGHT_HELPER_MARKER_RADIUS,
    LIGHT_HELPER_POINT_RADIUS,
    LIGHT_HELPER_SELECTED_BOOST,
    LIGHT_HELPER_SPOT_CAP_MAX_RADIUS,
    LIGHT_HELPER_SPOT_LENGTH,
)

_GR_GPU_PROBE = os.environ.get('GHOSTRIGGER_VIEWPORT_PROBE', '').strip().lower() in ('1', 'true', 'yes', 'on')
_GR_GPU_PROBE_SEEN: set = set()

_GL_STATE_TRACE_ENV = 'GHOSTRIGGER_GL_STATE_TRACE'
_GL_DEBUG_ERRORS_ENV = 'GHOSTRIGGER_GL_DEBUG_ERRORS'
_GL_STATE_TRACE_TRUE = ('1', 'true', 'yes', 'on')
_GL_STATE_TRACE_FALSE = ('', '0', 'false', 'no', 'off')
_GL_BACKEND_ENV = 'GHOSTRIGGER_GL_BACKEND'
_DEBUG_VIZ_ENV = 'GHOSTRIGGER_DEBUG_VIZ'
_LM_DATA_DUMP_ENV = 'GHOSTRIGGER_LM_DATA_DUMP'
_LM_COMPOSITE_MODE_ENV = 'GHOSTRIGGER_LM_COMPOSITE_MODE'
_SKIN_DUMP_ENV = 'GHOSTRIGGER_SKIN_DUMP'

_VBO_MAIN_FORMAT = '3f 3f 2f 2f 4f 4f'
_VBO_MAIN_ATTRS = ('in_pos', 'in_norm', 'in_uv', 'in_uv_lm', 'in_color', 'in_weights')
_VBO_BONE_IDS_FORMAT = '4i'
_VBO_BONE_IDS_ATTRS = ('in_bone_ids',)


def _hex_to_rgb_float(value: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return (
            int(raw[0:2], 16) / 255.0,
            int(raw[2:4], 16) / 255.0,
            int(raw[4:6], 16) / 255.0,
        )
    except ValueError:
        return fallback


def _gl_state_trace_path() -> str:
    """Return the JSONL trace path, or empty string when tracing is disabled."""
    raw = os.environ.get(_GL_STATE_TRACE_ENV, '').strip()
    if raw.lower() in _GL_STATE_TRACE_FALSE:
        return ''
    if raw.lower() in _GL_STATE_TRACE_TRUE:
        return os.path.abspath(os.path.join('exports', 'gl_state_trace.jsonl'))
    return os.path.abspath(raw)


def _lm_data_dump_path() -> str:
    """Return the lightmap data JSONL path, or empty string when disabled."""
    raw = os.environ.get(_LM_DATA_DUMP_ENV, '').strip()
    if raw.lower() in _GL_STATE_TRACE_FALSE:
        return ''
    if raw.lower() in _GL_STATE_TRACE_TRUE:
        return os.path.abspath(os.path.join('diagnostics', 'lm_data', 'lm_data.jsonl'))
    return os.path.abspath(raw)


def _skin_dump_path() -> str:
    """Return the skin parity JSONL path, or empty string when disabled."""
    raw = os.environ.get(_SKIN_DUMP_ENV, '').strip()
    if raw.lower() in _GL_STATE_TRACE_FALSE:
        return ''
    if raw.lower() in _GL_STATE_TRACE_TRUE:
        return os.path.abspath(os.path.join('diagnostics', 'skinning', 'skin_dump.jsonl'))
    return os.path.abspath(raw)


def _debug_visualize_mode() -> int:
    """Return debug visualization mode 0..4 from the environment."""
    raw = os.environ.get(_DEBUG_VIZ_ENV, '').strip()
    if not raw:
        return 0
    try:
        mode = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(4, mode))


def _lm_composite_mode() -> int:
    """Return lightmap composite diagnostic mode 0..3 from the environment."""
    raw = os.environ.get(_LM_COMPOSITE_MODE_ENV, '').strip()
    if not raw:
        return 0
    try:
        mode = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(3, mode))


def _jsonable_gl_value(value):
    """Convert ModernGL constants/uniform values to JSON-friendly data."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list)):
        return [_jsonable_gl_value(item) for item in value]
    try:
        return int(value)
    except Exception:
        return str(value)


def _safe_gl_attr(obj, name: str):
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _uniform_trace_value(uniforms: Dict[str, object], name: str):
    uniform = uniforms.get(name)
    if uniform is None:
        return None
    try:
        return _jsonable_gl_value(uniform.value)
    except Exception:
        return None


def _build_gl_state_trace_record(
        *,
        ctx,
        prog,
        node,
        pass_name: str,
        tri_count: int,
        blend_enabled: bool,
        tex_name: str,
        lm_name: str,
        env_name: str,
        spec_name: str,
        feature_mask: int,
        uniforms: Dict[str, object]) -> dict:
    """Build one draw-call GL state trace record."""
    node_name = str(getattr(node, 'name', '') or '')
    return {
        'event': 'draw',
        'time': time.time(),
        'pass': pass_name,
        'node': node_name,
        'program_id': id(prog),
        'tri_count': int(tri_count or 0),
        'texture': tex_name,
        'lightmap': lm_name,
        'envmap': env_name,
        'specular': spec_name,
        'gl_depth_test': True,  # renderer enables DEPTH_TEST at frame start
        'gl_depth_func': _jsonable_gl_value(_safe_gl_attr(ctx, 'depth_func')),
        'gl_depth_writemask': False if pass_name == 'transparent' else True,
        'gl_cull_face': True,  # renderer enables CULL_FACE at frame start
        'gl_cull_face_mode': _jsonable_gl_value(_safe_gl_attr(ctx, 'cull_face')),
        'gl_front_face': _jsonable_gl_value(_safe_gl_attr(ctx, 'front_face')),
        'gl_blend_enabled': bool(blend_enabled),
        'gl_blend_func': _jsonable_gl_value(_safe_gl_attr(ctx, 'blend_func')),
        'gl_blend_equation': _jsonable_gl_value(_safe_gl_attr(ctx, 'blend_equation')),
        'transparency_hint': int(getattr(node, 'transparency_hint', 0) or 0),
        'txi_blending': int(getattr(node, 'txi_blending', 0) or 0),
        'txi_alpha_test': float(getattr(node, 'txi_alpha_test', 0.0) or 0.0),
        'txi_wateralpha': float(getattr(node, 'txi_wateralpha', 1.0) or 1.0),
        'txi_decal': bool(getattr(node, 'txi_decal', False)),
        'is_skin': bool(getattr(node, 'is_skin', False)),
        'is_dangly': bool(getattr(node, 'is_dangly', False)),
        'is_face_mesh_name': any(s in node_name.lower() for s in _FACE_MESH_SUBSTRINGS),
        'is_inner_geometry_name': any(s in node_name.lower() for s in _INNER_GEO_SUBSTRINGS),
        'u_alpha': _uniform_trace_value(uniforms, 'u_alpha'),
        'u_node_alpha': _uniform_trace_value(uniforms, 'u_node_alpha'),
        'u_blend_mode': _uniform_trace_value(uniforms, 'u_blend_mode'),
        'u_alpha_test': _uniform_trace_value(uniforms, 'u_alpha_test'),
        'u_wateralpha': _uniform_trace_value(uniforms, 'u_wateralpha'),
        'u_oit_enabled': _uniform_trace_value(uniforms, 'u_oit_enabled'),
        'u_debug_visualize': _uniform_trace_value(uniforms, 'u_debug_visualize'),
        'u_lm_composite_mode': _uniform_trace_value(uniforms, 'u_lm_composite_mode'),
        'u_has_tex': _uniform_trace_value(uniforms, 'u_has_tex'),
        'u_has_lm': _uniform_trace_value(uniforms, 'u_has_lm'),
        'u_has_env': _uniform_trace_value(uniforms, 'u_has_env'),
        'u_lm_shade': _uniform_trace_value(uniforms, 'u_lm_shade'),
        'u_features': int(feature_mask or 0),
    }


def _append_gl_state_trace(path: str, record: dict) -> None:
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(record, sort_keys=True) + '\n')
    except Exception as exc:
        log.debug("GL state trace write failed: %s", exc)


def _first_uv_pairs(values, limit: int = 8) -> List[List[float]]:
    out: List[List[float]] = []
    for uv in list(values or [])[:limit]:
        try:
            out.append([float(uv[0]), float(uv[1])])
        except Exception:
            out.append([0.0, 0.0])
    return out


def _first_vbo_uv_pairs(vdata, start: int, limit: int = 8) -> List[List[float]]:
    if vdata is None:
        return []
    try:
        rows = vdata[:limit, start:start + 2]
        return [[float(row[0]), float(row[1])] for row in rows]
    except Exception:
        return []


def _node_uses_single_tile_atlas(node) -> bool:
    """Return True for ordinary 0..1 character atlases that should not repeat."""
    if bool(getattr(node, 'txi_clamp_s', False) and getattr(node, 'txi_clamp_t', False)):
        return True
    if bool(getattr(node, 'animate_uv', False)):
        return False
    if str(getattr(node, 'txi_proceduretype', '') or '').strip():
        return False
    if int(getattr(node, 'txi_blending', 0) or 0) != 0:
        return False
    uvs = getattr(node, 'uvs', []) or []
    if not uvs:
        return False
    try:
        return all(0.0 <= float(u) <= 1.0 and 0.0 <= float(v) <= 1.0 for u, v in uvs)
    except Exception:
        return False


def _should_auto_clamp_diffuse(node, *, is_module: bool = False) -> bool:
    """Return True when GhostRigger should clamp a diffuse atlas without TXI flags.

    Module/area models often use ordinary-looking 0..1 UV islands alongside tiled
    room textures and baked lightmaps.  Their diffuse textures should keep the
    engine default repeat mode unless the TXI explicitly requests clamping.  The
    heuristic clamp exists for character/item atlases such as custom Mandalorian
    bodies, not for area geometry.
    """
    if is_module:
        return False
    return _node_uses_single_tile_atlas(node)


def _texture_content_stats(img) -> Optional[dict]:
    if img is None or not _PIL:
        return None
    try:
        rgba = img.convert('RGBA')
        data = rgba.tobytes()
        w, h = rgba.size
        if _NUMPY:
            arr = np.asarray(rgba, dtype=np.uint8)
            rgb = arr[:, :, :3]
            min_rgb = [int(v) for v in rgb.reshape(-1, 3).min(axis=0)]
            max_rgb = [int(v) for v in rgb.reshape(-1, 3).max(axis=0)]
            mean_rgb = [round(float(v), 4) for v in rgb.reshape(-1, 3).mean(axis=0)]
            alpha = arr[:, :, 3]
            alpha_range = [int(alpha.min()), int(alpha.max())]
        else:
            pixels = list(rgba.getdata())
            rgb_vals = [p[:3] for p in pixels]
            min_rgb = [min(p[i] for p in rgb_vals) for i in range(3)]
            max_rgb = [max(p[i] for p in rgb_vals) for i in range(3)]
            mean_rgb = [round(sum(p[i] for p in rgb_vals) / max(1, len(rgb_vals)), 4)
                        for i in range(3)]
            alpha_vals = [p[3] for p in pixels]
            alpha_range = [min(alpha_vals), max(alpha_vals)]

        def _sample(x0: int, y0: int) -> List[List[List[int]]]:
            rows: List[List[List[int]]] = []
            for yy in range(y0, min(y0 + 4, h)):
                row: List[List[int]] = []
                for xx in range(x0, min(x0 + 4, w)):
                    row.append([int(v) for v in rgba.getpixel((xx, yy))])
                rows.append(row)
            return rows

        return {
            'mode': getattr(img, 'mode', ''),
            'decoded_pixel_format': 'RGBA8',
            'size': [int(w), int(h)],
            'sha256_rgba': hashlib.sha256(data).hexdigest(),
            'min_rgb': min_rgb,
            'max_rgb': max_rgb,
            'mean_rgb': mean_rgb,
            'alpha_range': alpha_range,
            'corner_4x4_rgba': {
                'top_left': _sample(0, 0),
                'top_right': _sample(max(0, w - 4), 0),
                'bottom_left': _sample(0, max(0, h - 4)),
                'bottom_right': _sample(max(0, w - 4), max(0, h - 4)),
            },
        }
    except Exception as exc:
        return {'error': str(exc)}


def _lightmap_role_info(node, has_lm_flag: bool, lightmap_bound: bool) -> dict:
    tex_count = int(getattr(node, 'tex_count', 1) or 1)
    tex_names = getattr(node, 'texture_names', []) or []
    uvs = getattr(node, 'uvs', []) or []
    uvs_lm = getattr(node, 'uvs_lm', []) or []
    face_mats = getattr(node, 'face_mats', []) or []
    authored_has_lm = bool(getattr(node, 'has_lightmap', False))
    lm_name = str(getattr(node, 'lightmap', '') or '').strip().lower()
    inferred = bool(
        not authored_has_lm
        and lm_name
        and len(uvs_lm) > 0
        and tex_count >= 2
    )
    effective_lm = bool(has_lm_flag)
    if tex_count <= 1 or len(tex_names) < tex_count:
        dispatch = 'single'
        slot1_role = 'N/A'
    elif effective_lm:
        dispatch = 'Case A'
        slot1_role = 'lightmap'
    else:
        dispatch = 'Case B'
        slot1_role = 'secondary diffuse'
    return {
        'has_lightmap': authored_has_lm,
        'lightmap_role_inferred': inferred,
        'effective_lightmap': effective_lm,
        'dispatch_path': dispatch,
        'slot1_role': slot1_role,
        'tex_count': tex_count,
        'texture_names_count': len(tex_names),
        'face_mats_unique': sorted({int(m) for m in face_mats})[:16] if face_mats else [],
        'len_uvs': len(uvs),
        'len_uvs_lm': len(uvs_lm),
        'lightmap_bound': bool(lightmap_bound),
    }


def _build_lm_data_dump_record(
        *,
        ctx,
        prog,
        node,
        pass_name: str,
        gm,
        has_lm_flag: bool,
        lightmap_bound: bool,
        lm_img,
        lm_name: str,
        uniforms: Dict[str, object]) -> dict:
    """Build one lightmap data-path diagnostic record."""
    verts = getattr(node, 'vertices', getattr(node, 'verts', [])) or []
    uvs = getattr(node, 'uvs', []) or []
    uvs_lm = getattr(node, 'uvs_lm', []) or []
    role = _lightmap_role_info(node, has_lm_flag, lightmap_bound)
    record = {
        'event': 'lightmap_draw',
        'time': time.time(),
        'pass': pass_name,
        'node': str(getattr(node, 'name', '') or ''),
        'program_id': id(prog),
        'vertex_count': len(verts),
        'uploaded_vertex_count': int(getattr(gm, 'uploaded_vertex_count', 0) or 0),
        'len_uvs': len(uvs),
        'len_uvs_lm': len(uvs_lm),
        'first8_uv0_model': _first_uv_pairs(uvs),
        'first8_uv1_model': _first_uv_pairs(uvs_lm),
        'first8_uv0_uploaded': list(getattr(gm, 'first8_uv0_uploaded', []) or []),
        'first8_uv1_uploaded': list(getattr(gm, 'first8_uv1_uploaded', []) or []),
        'lightmap_texture_name': lm_name,
        'lightmap_texture_stats': _texture_content_stats(lm_img),
        'uv1_attribute_bound': bool(getattr(gm, 'uv1_attribute_bound', False)),
        'uv1_vbo_id': id(getattr(gm, 'vbo', None)) if getattr(gm, 'vbo', None) is not None else None,
        'lightmap_uniforms': {
            'u_has_lm': _uniform_trace_value(uniforms, 'u_has_lm'),
            'u_lm_shade': _uniform_trace_value(uniforms, 'u_lm_shade'),
            'u_lm_tex': _uniform_trace_value(uniforms, 'u_lm_tex'),
            'u_debug_visualize': _uniform_trace_value(uniforms, 'u_debug_visualize'),
            'u_lm_composite_mode': _uniform_trace_value(uniforms, 'u_lm_composite_mode'),
        },
    }
    record.update(role)
    return record


def _append_jsonl_record(path: str, record: dict, label: str) -> None:
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(record, sort_keys=True) + '\n')
    except Exception as exc:
        log.debug("%s write failed: %s", label, exc)


def _matrix4_json(matrix) -> List[List[float]]:
    if matrix is None:
        return []
    try:
        return [[round(float(v), 6) for v in row] for row in matrix]
    except Exception:
        return []


def _matrix4_inverse_json(matrix) -> List[List[float]]:
    if matrix is None or not _NUMPY:
        return []
    try:
        return _matrix4_json(np.linalg.inv(np.asarray(matrix, dtype=np.float64)))
    except Exception:
        return []


def _matrix4_mul_json(a, b) -> List[List[float]]:
    if a is None or b is None or not _NUMPY:
        return []
    try:
        return _matrix4_json(np.asarray(a, dtype=np.float64) @ np.asarray(b, dtype=np.float64))
    except Exception:
        return []


def _matrix4_det_value(matrix) -> Optional[float]:
    if matrix is None or not _NUMPY:
        return None
    try:
        return round(float(np.linalg.det(np.asarray(matrix, dtype=np.float64))), 6)
    except Exception:
        return None


def _qbone_inverse_bind_json(node, local_idx: int) -> List[List[float]]:
    if not _NUMPY:
        return []
    qbones = getattr(node, 'qbone_list', []) or []
    tbones = getattr(node, 'tbone_list', []) or []
    if local_idx < 0 or local_idx >= len(qbones) or local_idx >= len(tbones):
        return []
    try:
        x, y, z, w = (float(v) for v in qbones[local_idx])
        tx, ty, tz = (float(v) for v in tbones[local_idx])
        qlen = math.sqrt(x*x + y*y + z*z + w*w)
        if qlen > 1e-9:
            x, y, z, w = x/qlen, y/qlen, z/qlen, w/qlen
        else:
            x, y, z, w = 0.0, 0.0, 0.0, 1.0
        xx, yy, zz = 2*x*x, 2*y*y, 2*z*z
        xy, xz, yz = 2*x*y, 2*x*z, 2*y*z
        wx, wy, wz = 2*w*x, 2*w*y, 2*w*z
        m = np.array([
            [1-yy-zz, xy-wz,   xz+wy,   tx],
            [xy+wz,   1-xx-zz, yz-wx,   ty],
            [xz-wy,   yz+wx,   1-xx-yy, tz],
            [0.0,     0.0,     0.0,     1.0],
        ], dtype=np.float64)
        return _matrix4_json(np.linalg.inv(m))
    except Exception:
        return []


def _qbone_direct_bind_json(node, local_idx: int) -> List[List[float]]:
    if not _NUMPY:
        return []
    qbones = getattr(node, 'qbone_list', []) or []
    tbones = getattr(node, 'tbone_list', []) or []
    if local_idx < 0 or local_idx >= len(qbones) or local_idx >= len(tbones):
        return []
    try:
        return _matrix4_json(_qbone_matrix_np(node, local_idx, order='TR', inverse=False))
    except Exception:
        return []


def _uploaded_palette_array_from_uploader(uploader):
    if uploader is None or not _NUMPY:
        return None
    try:
        raw = uploader.as_flat_bytes()
        arr = np.frombuffer(raw, dtype=np.float32).reshape((-1, 16))
        out = np.zeros((len(arr), 4, 4), dtype=np.float32)
        for idx, col in enumerate(arr):
            for r in range(4):
                for c in range(4):
                    out[idx, r, c] = col[c * 4 + r]
        return out
    except Exception:
        return None


def _pose_node_transform(anim_pose, node) -> dict:
    name = str(getattr(node, 'name', '') or '').lower()
    pn = None
    if anim_pose is not None and hasattr(anim_pose, 'nodes'):
        pn = anim_pose.nodes.get(name)
    if pn is not None:
        pos = getattr(pn, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
        rot = getattr(pn, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
    else:
        pos = getattr(node, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
        rot = getattr(node, 'rotation', (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)
    return {
        'position': [float(v) for v in pos[:3]],
        'rotation': [float(v) for v in rot[:4]],
        'has_anim_pose': pn is not None,
    }


def _select_skin_probe_vertex(node) -> int:
    skin_data = getattr(node, 'skin_data', []) or []
    best_idx = 0
    best_score = -1.0
    for idx, skin in enumerate(skin_data):
        influences = list(getattr(skin, 'influences', []) or [])
        if not influences:
            continue
        weight_sum = sum(float(getattr(inf, 'weight', 0.0) or 0.0) for inf in influences)
        score = len(influences) * 10.0 + weight_sum
        if score > best_score:
            best_idx = idx
            best_score = score
    return best_idx


def _matrix_from_pos_quat_np(pos, quat):
    if not _NUMPY:
        return None
    try:
        tx, ty, tz = (float(v) for v in (pos or (0.0, 0.0, 0.0))[:3])
        x, y, z, w = (float(v) for v in (quat or (0.0, 0.0, 0.0, 1.0))[:4])
        qlen = math.sqrt(x*x + y*y + z*z + w*w)
        if qlen > 1e-9:
            x, y, z, w = x/qlen, y/qlen, z/qlen, w/qlen
        else:
            x, y, z, w = 0.0, 0.0, 0.0, 1.0
        xx, yy, zz = 2*x*x, 2*y*y, 2*z*z
        xy, xz, yz = 2*x*y, 2*x*z, 2*y*z
        wx, wy, wz = 2*w*x, 2*w*y, 2*w*z
        return np.array([
            [1-yy-zz, xy-wz,   xz+wy,   tx],
            [xy+wz,   1-xx-zz, yz-wx,   ty],
            [xz-wy,   yz+wx,   1-xx-yy, tz],
            [0.0,     0.0,     0.0,     1.0],
        ], dtype=np.float64)
    except Exception:
        return np.eye(4, dtype=np.float64)


def _qbone_matrix_np(node, local_idx: int, *, order: str, inverse: bool):
    if not _NUMPY:
        return None
    qbones = getattr(node, 'qbone_list', []) or []
    tbones = getattr(node, 'tbone_list', []) or []
    if local_idx < 0 or local_idx >= len(qbones) or local_idx >= len(tbones):
        return np.eye(4, dtype=np.float64)
    q = qbones[local_idx]
    t = tbones[local_idx]
    rot = _matrix_from_pos_quat_np((0.0, 0.0, 0.0), q)
    trans = _matrix_from_pos_quat_np(t, (0.0, 0.0, 0.0, 1.0))
    mat = (trans @ rot) if order == 'TR' else (rot @ trans)
    if inverse:
        try:
            return np.linalg.inv(mat)
        except Exception:
            return np.eye(4, dtype=np.float64)
    return mat


def _node_world_matrix_for_pose_np(node, anim_pose, cache: Dict[int, object]):
    if not _NUMPY:
        return None
    if node is None:
        return np.eye(4, dtype=np.float64)
    node_id = id(node)
    if node_id in cache:
        return cache[node_id]
    pose = None
    name = str(getattr(node, 'name', '') or '').lower()
    if anim_pose is not None and hasattr(anim_pose, 'nodes'):
        pose = anim_pose.nodes.get(name)
    if pose is not None:
        pos = getattr(pose, 'position', (0.0, 0.0, 0.0))
        quat = getattr(pose, 'rotation', (0.0, 0.0, 0.0, 1.0))
    else:
        pos = getattr(node, 'position', (0.0, 0.0, 0.0))
        quat = getattr(node, 'rotation', (0.0, 0.0, 0.0, 1.0))
    local = _matrix_from_pos_quat_np(pos, quat)
    parent = getattr(node, 'parent', None)
    if parent is not None:
        mat = _node_world_matrix_for_pose_np(parent, anim_pose, cache) @ local
    else:
        mat = local
    cache[node_id] = mat
    return mat


def _node_parent_chain_names(node) -> List[str]:
    chain = []
    cur = node
    while cur is not None:
        chain.append(str(getattr(cur, 'name', '') or ''))
        cur = getattr(cur, 'parent', None)
    return list(reversed([name for name in chain if name]))


def _node_pose_chain_records(node, anim_pose) -> List[dict]:
    if node is None or not _NUMPY:
        return []
    chain = []
    cur = node
    while cur is not None:
        chain.append(cur)
        cur = getattr(cur, 'parent', None)
    records = []
    for chain_node in reversed(chain):
        records.append({
            'node_name': str(getattr(chain_node, 'name', '') or ''),
            'bind_local': _pose_node_transform(None, chain_node),
            'animated_local': _pose_node_transform(anim_pose, chain_node),
            'animated_world_matrix': _matrix4_json(
                _node_world_matrix_for_pose_np(chain_node, anim_pose, {})
            ),
        })
    return records


_SKIN_3G_FORMULAS = {
    'F1_current_TR_inverse': 'animated_world * inverse(T * R)',
    'F2_RT_inverse': 'animated_world * inverse(R * T)',
    'F3_skin_bind_pre': 'skin_node_bind * animated_world * inverse(T * R)',
    'F4_skin_bind_post_inverse': 'animated_world * inverse(T * R) * inverse(skin_node_bind)',
    'F5_skin_bind_precancel': 'inverse(skin_node_bind) * animated_world * inverse(T * R)',
    'F6_TR_direct': 'animated_world * (T * R)',
    'F7_RT_direct': 'animated_world * (R * T)',
    'F8_bind_wrapper': 'inverse(skin_node_bind) * animated_world * inverse(T * R) * skin_node_bind',
    'F9_xoreos_TR_direct_wrapper': 'inverse(skin_node_bind) * animated_world * (T * R) * skin_node_bind',
    'F10_RT_direct_wrapper': 'inverse(skin_node_bind) * animated_world * (R * T) * skin_node_bind',
    # 3i Step 7 - B-translation diagnostic candidates
    'F11_rotation_only_skin_bind_wrapper': (
        'inverse(R(skin_node_bind)) * animated_world * inverse(T * R) * R(skin_node_bind)'
    ),
    'F12_xoreos_first_frame_orientation_wrapper': (
        'inverse(M_chain) * animated_world * inverse(T * R) * M_chain   '
        'where M_chain = composed first-frame orientations of skin_node parent chain '
        '(xoreos ModelNode::computeInverseBindPose L891-919)'
    ),
}


def _quat_xyzw_to_mat4_np(qx: float, qy: float, qz: float, qw: float):
    """Convert an XYZW quaternion to a row-major 4x4 numpy rotation matrix.

    Uses the same XYZW convention enforced project-wide
    (see ``project-identity.mdc`` constraint #5).  Identity quats and
    near-zero norms collapse to the identity matrix safely.
    """
    if not _NUMPY:
        return None
    ql2 = qx * qx + qy * qy + qz * qz + qw * qw
    if ql2 > 1e-9:
        inv_l = 1.0 / float(np.sqrt(ql2))
        qx, qy, qz, qw = qx * inv_l, qy * inv_l, qz * inv_l, qw * inv_l
    else:
        qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0
    m = np.eye(4, dtype=np.float64)
    m[0, 0] = 1.0 - 2.0 * (qy * qy + qz * qz)
    m[0, 1] = 2.0 * (qx * qy - qz * qw)
    m[0, 2] = 2.0 * (qx * qz + qy * qw)
    m[1, 0] = 2.0 * (qx * qy + qz * qw)
    m[1, 1] = 1.0 - 2.0 * (qx * qx + qz * qz)
    m[1, 2] = 2.0 * (qy * qz - qx * qw)
    m[2, 0] = 2.0 * (qx * qz - qy * qw)
    m[2, 1] = 2.0 * (qy * qz + qx * qw)
    m[2, 2] = 1.0 - 2.0 * (qx * qx + qy * qy)
    return m


def _xoreos_first_frame_orientation_matrix(skin_node, anim_pose):
    """Build xoreos's pre-wrapper outer transform for ``skin_node``.

    Reproduces ``ModelNode::computeInverseBindPose()`` (xoreos lines 891-919):

    1. Walk parents from ``skin_node`` to root.
    2. Iterate root-first and right-multiply each node's first-frame
       orientation into an accumulator (translation frames are read but
       intentionally never applied — see lines 904-907).
    3. xoreos then inverts to produce ``_invBindPose``; this helper
       returns the *uninverted* accumulator so the caller can use it as
       ``transform = inverse(_invBindPose)`` directly (xoreos's outer
       multiplier).

    When ``anim_pose`` is provided the per-node rotation is taken from the
    pose's first-frame snapshot; otherwise the static bind rotation is
    used as a fallback.  Returns a 4x4 numpy matrix or ``None`` when
    NumPy is unavailable.
    """
    if not _NUMPY or skin_node is None:
        return None
    chain = []
    n = skin_node
    visited = set()
    while n is not None and id(n) not in visited:
        visited.add(id(n))
        chain.append(n)
        n = getattr(n, 'parent', None)
    chain.reverse()  # root-first
    pose_nodes = (
        {str(k).lower(): v for k, v in getattr(anim_pose, 'nodes', {}).items()}
        if anim_pose is not None else {}
    )
    accum = np.eye(4, dtype=np.float64)
    for node in chain:
        name = str(getattr(node, 'name', '') or '').lower()
        rot = None
        if name and name in pose_nodes:
            rot = getattr(pose_nodes[name], 'rotation', None)
        if rot is None:
            rot = getattr(node, 'rotation', (0.0, 0.0, 0.0, 1.0))
        if rot is None:
            rot = (0.0, 0.0, 0.0, 1.0)
        try:
            qx, qy, qz, qw = float(rot[0]), float(rot[1]), float(rot[2]), float(rot[3])
        except Exception:
            continue
        # xoreos skips rotate when (x,y,z) all zero — matches identity quat case.
        if qx == 0.0 and qy == 0.0 and qz == 0.0:
            continue
        rot_m = _quat_xyzw_to_mat4_np(qx, qy, qz, qw)
        if rot_m is None:
            continue
        accum = accum @ rot_m
    return accum


def _skin_3g_matrix_for_formula(formula: str, skin_bind, animated_world, q_tr_inv,
                                q_rt_inv, q_tr_direct, q_rt_direct,
                                rot_only_skin_bind=None,
                                xoreos_first_frame_outer=None):
    try:
        inv_skin = np.linalg.inv(skin_bind)
    except Exception:
        inv_skin = np.eye(4, dtype=np.float64)
    if formula == 'F1_current_TR_inverse':
        return animated_world @ q_tr_inv
    if formula == 'F2_RT_inverse':
        return animated_world @ q_rt_inv
    if formula == 'F3_skin_bind_pre':
        return skin_bind @ animated_world @ q_tr_inv
    if formula == 'F4_skin_bind_post_inverse':
        return animated_world @ q_tr_inv @ inv_skin
    if formula == 'F5_skin_bind_precancel':
        return inv_skin @ animated_world @ q_tr_inv
    if formula == 'F6_TR_direct':
        return animated_world @ q_tr_direct
    if formula == 'F7_RT_direct':
        return animated_world @ q_rt_direct
    if formula == 'F8_bind_wrapper':
        return inv_skin @ animated_world @ q_tr_inv @ skin_bind
    if formula == 'F9_xoreos_TR_direct_wrapper':
        return inv_skin @ animated_world @ q_tr_direct @ skin_bind
    if formula == 'F10_RT_direct_wrapper':
        return inv_skin @ animated_world @ q_rt_direct @ skin_bind
    if formula == 'F11_rotation_only_skin_bind_wrapper':
        outer = rot_only_skin_bind if rot_only_skin_bind is not None else skin_bind
        try:
            inv_outer = np.linalg.inv(outer)
        except Exception:
            inv_outer = np.eye(4, dtype=np.float64)
        return inv_outer @ animated_world @ q_tr_inv @ outer
    if formula == 'F12_xoreos_first_frame_orientation_wrapper':
        outer = (
            xoreos_first_frame_outer
            if xoreos_first_frame_outer is not None else skin_bind
        )
        try:
            inv_outer = np.linalg.inv(outer)
        except Exception:
            inv_outer = np.eye(4, dtype=np.float64)
        return inv_outer @ animated_world @ q_tr_inv @ outer
    return animated_world @ q_tr_inv


def _skin_3g_role_for_bone(bone_name: str) -> str:
    name = str(bone_name or '').lower()
    if any(tok in name for tok in ('head', 'jaw', 'tooth', 'pincher')):
        return 'head'
    if any(tok in name for tok in ('forearm', 'upperarm', 'bicep', 'hand', 'finger', 'thumb')):
        return 'forelimb'
    if 'wing_01' in name or 'wing_bone_1' in name or name.endswith('wing_1'):
        return 'wing_root'
    if any(tok in name for tok in ('pelvis', 'lowerbody', 'torso')):
        return 'pelvis'
    return ''


def _skin_3g_role_priority(bone_name: str, role: str) -> float:
    name = str(bone_name or '').lower()
    if role == 'head':
        if 'head' in name:
            return 3.0
        if 'jaw' in name or 'neck' in name:
            return 2.0
        return 1.0
    if role == 'forelimb':
        if 'forearm' in name:
            return 3.0
        if 'upperarm' in name or 'bicep' in name:
            return 2.0
        return 1.0
    if role == 'wing_root':
        if 'wing_01' in name or 'wing_bone_1' in name:
            return 3.0
        return 1.0
    if role == 'pelvis':
        if 'pelvis' in name or 'lowerbody' in name:
            return 3.0
        return 1.0
    return 0.0


def _select_skin_3g_probe_vertices(node, bone_map: List[str], skin_data: List[object]) -> List[dict]:
    best: Dict[str, dict] = {}
    for vi, skin in enumerate(skin_data):
        influences = list(getattr(skin, 'influences', []) or [])
        for inf in influences:
            local_idx = int(getattr(inf, 'bone_index', 0) or 0)
            if local_idx < 0 or local_idx >= len(bone_map):
                continue
            weight = float(getattr(inf, 'weight', 0.0) or 0.0)
            role = _skin_3g_role_for_bone(bone_map[local_idx])
            if not role:
                continue
            # Prefer the intended anatomical discriminator over a nearby helper
            # with the same weight (e.g. head_g over LPincher, wing_01 over wing_02).
            score = weight + (_skin_3g_role_priority(bone_map[local_idx], role) * 0.01)
            current = best.get(role)
            if current is None or score > current['score']:
                best[role] = {
                    'vertex_role': role,
                    'vertex_index': vi,
                    'dominant_local_bone_index': local_idx,
                    'dominant_bone_name': bone_map[local_idx],
                    'score': score,
                }
    return [
        {k: v for k, v in rec.items() if k != 'score'}
        for _role, rec in sorted(best.items())
    ]


def _homogeneous_position_json(vec) -> List[float]:
    if vec is None:
        return []
    try:
        arr = np.asarray(vec, dtype=np.float64)
        denom = float(arr[3]) if arr.shape[0] > 3 and abs(float(arr[3])) > 1e-9 else 1.0
        return [round(float(v) / denom, 6) for v in arr[:3]]
    except Exception:
        return []


def _first_divergence_stage(stage_pairs: List[Tuple[str, object, object]], tolerance: float = 1e-4) -> str:
    if not _NUMPY:
        return "unavailable_numpy"
    for name, left, right in stage_pairs:
        try:
            a = np.asarray(left, dtype=np.float64)
            b = np.asarray(right, dtype=np.float64)
            if a.shape != b.shape or float(np.max(np.abs(a - b))) > tolerance:
                return name
        except Exception:
            return name
    return "none_within_tolerance"


def _matrix_max_abs_delta(a, b) -> Optional[float]:
    if a is None or b is None or not _NUMPY:
        return None
    try:
        return round(float(np.max(np.abs(
            np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
        ))), 6)
    except Exception:
        return None


def _matrix_translation_norm(matrix) -> Optional[float]:
    """L2 norm of the translation column of a 4x4 matrix.

    Used by 3i Step 6 to quantify how much position content lives in
    GhostRigger's ``skin_bind``.  xoreos's pre-wrapper ``transform`` is
    rotation-only (positions are read but not applied — see
    ``ModelNode::computeInverseBindPose`` lines 891-919), so any non-zero
    translation here is a structural composition mismatch.
    """
    if matrix is None or not _NUMPY:
        return None
    try:
        m = np.asarray(matrix, dtype=np.float64)
        if m.shape != (4, 4):
            return None
        return round(float(np.linalg.norm(m[:3, 3])), 6)
    except Exception:
        return None


def _matrix_rotation_only(matrix):
    """Return ``matrix`` with the translation column zeroed (W=1 kept).

    Used as a stand-in for xoreos's rotation-only ``inverse(_invBindPose)``
    when probing whether GhostRigger's full-pose ``skin_bind`` is the
    structural source of the wrapper visual failure.  Returned as a numpy
    array (not JSON) so callers can multiply by a homogeneous vertex.
    """
    if matrix is None or not _NUMPY:
        return None
    try:
        m = np.asarray(matrix, dtype=np.float64).copy()
        if m.shape != (4, 4):
            return None
        m[:3, 3] = 0.0
        m[3, :3] = 0.0
        m[3, 3] = 1.0
        return m
    except Exception:
        return None


def _skin_bind_equivalence_record(node, uploader) -> dict:
    current = getattr(uploader, '_skin_bind_matrix', None) if uploader is not None else None
    node_world = _node_world_matrix_for_pose_np(node, None, {}) if _NUMPY else None
    parent = getattr(node, 'parent', None)
    parent_world = _node_world_matrix_for_pose_np(parent, None, {}) if parent is not None and _NUMPY else None
    identity = np.eye(4, dtype=np.float64) if _NUMPY else None
    # KotOR.js calls SkinnedMesh.bind(skeleton) with no explicit bindMatrix.
    # Three.js therefore captures the SkinnedMesh's current matrixWorld.
    kotorjs_default = node_world
    candidates = {
        'kotorjs_default_mesh_matrixWorld': kotorjs_default,
        'ghostrigger_node_world_bind': node_world,
        'parent_world_bind': parent_world,
        'identity_bind': identity,
    }
    return {
        'reference_renderer': 'KotOR.js/Three.js',
        'reference_source': 'OdysseyModel3D.ts buildSkeleton skinNode.bind(new THREE.Skeleton(bones, inverses))',
        'reference_bind_semantics': 'Three.js SkinnedMesh.bind without bindMatrix captures mesh.matrixWorld',
        'ghostrigger_current_skin_bind_matrix': _matrix4_json(current),
        'candidate_matrices': {
            name: _matrix4_json(matrix)
            for name, matrix in candidates.items()
        },
        'candidate_vs_current_max_abs': {
            name: _matrix_max_abs_delta(current, matrix)
            for name, matrix in candidates.items()
        },
        'candidate_vs_kotorjs_default_max_abs': {
            name: _matrix_max_abs_delta(kotorjs_default, matrix)
            for name, matrix in candidates.items()
        },
    }


def _skin_3g_candidate_records(*, model, node, bone_map: List[str],
                               skin_data: List[object], vertices: List[object],
                               anim_pose, uploaded_palette_arr,
                               uploaded_positions: Optional[List[List[float]]] = None,
                               uploaded_bone_ids: Optional[List[List[int]]] = None,
                               uploaded_weights: Optional[List[List[float]]] = None,
                               uploaded_source_indices: Optional[List[int]] = None) -> List[dict]:
    if not _NUMPY or not bone_map or not skin_data or not vertices:
        return []
    probes = _select_skin_3g_probe_vertices(node, bone_map, skin_data)
    if not probes:
        return []
    skin_bind = _node_world_matrix_for_pose_np(node, None, {})
    skin_pose = _node_world_matrix_for_pose_np(node, anim_pose, {})
    # 3i Step 7 - B-translation diagnostic outer matrices
    skin_bind_rot_only = _matrix_rotation_only(skin_bind)
    xoreos_first_frame_outer = _xoreos_first_frame_orientation_matrix(node, anim_pose)
    lookup = {}
    try:
        lookup = {str(getattr(n, 'name', '') or '').lower(): n for n in model.all_nodes()}
    except Exception:
        lookup = {}
    out = []
    for probe in probes:
        vi = int(probe['vertex_index'])
        if vi < 0 or vi >= len(vertices) or vi >= len(skin_data):
            continue
        raw = np.array([float(v) for v in vertices[vi][:3]], dtype=np.float64)
        vbo = raw.copy()
        vbo_row_index = vi
        if uploaded_source_indices is not None:
            try:
                vbo_row_index = uploaded_source_indices.index(vi)
            except ValueError:
                vbo_row_index = vi
        if uploaded_positions is not None and 0 <= vbo_row_index < len(uploaded_positions):
            try:
                vbo = np.array([float(v) for v in uploaded_positions[vbo_row_index][:3]], dtype=np.float64)
            except Exception:
                vbo = raw.copy()
        hv = np.array([raw[0], raw[1], raw[2], 1.0], dtype=np.float64)
        hv_vbo = np.array([vbo[0], vbo[1], vbo[2], 1.0], dtype=np.float64)
        skin = skin_data[vi]
        influences = list(getattr(skin, 'influences', []) or [])[:4]
        formula_acc = {name: np.zeros(4, dtype=np.float64) for name in _SKIN_3G_FORMULAS}
        gpu_acc = np.zeros(4, dtype=np.float64)
        production_qbone_acc = np.zeros(4, dtype=np.float64)
        production_weighted_acc = np.zeros(4, dtype=np.float64)
        reference_f8_skin_bind_acc = np.zeros(4, dtype=np.float64)
        reference_f8_qbone_acc = np.zeros(4, dtype=np.float64)
        reference_f8_animated_acc = np.zeros(4, dtype=np.float64)
        reference_f8_weighted_acc = np.zeros(4, dtype=np.float64)
        reference_f9_qbone_acc = np.zeros(4, dtype=np.float64)
        reference_f9_animated_acc = np.zeros(4, dtype=np.float64)
        reference_f9_weighted_acc = np.zeros(4, dtype=np.float64)
        try:
            inv_skin_bind = np.linalg.inv(skin_bind)
        except Exception:
            inv_skin_bind = np.eye(4, dtype=np.float64)
        influence_records = []
        for inf in influences:
            local_idx = int(getattr(inf, 'bone_index', 0) or 0)
            weight = float(getattr(inf, 'weight', 0.0) or 0.0)
            bone_name = bone_map[local_idx] if 0 <= local_idx < len(bone_map) else ''
            bone_node = lookup.get(str(bone_name).lower()) if bone_name else None
            animated_world = _node_world_matrix_for_pose_np(bone_node, anim_pose, {})
            q_tr_inv = _qbone_matrix_np(node, local_idx, order='TR', inverse=True)
            q_rt_inv = _qbone_matrix_np(node, local_idx, order='RT', inverse=True)
            q_tr_direct = _qbone_matrix_np(node, local_idx, order='TR', inverse=False)
            q_rt_direct = _qbone_matrix_np(node, local_idx, order='RT', inverse=False)
            production_qbone_h = q_tr_inv @ hv_vbo
            production_animated_h = animated_world @ production_qbone_h
            reference_skin_bind_h = skin_bind @ hv_vbo
            reference_f8_qbone_h = q_tr_inv @ reference_skin_bind_h
            reference_f8_animated_h = animated_world @ reference_f8_qbone_h
            reference_f8_final_h = inv_skin_bind @ reference_f8_animated_h
            reference_f9_qbone_h = q_tr_direct @ reference_skin_bind_h
            reference_f9_animated_h = animated_world @ reference_f9_qbone_h
            reference_f9_final_h = inv_skin_bind @ reference_f9_animated_h
            production_qbone_acc += weight * production_qbone_h
            production_weighted_acc += weight * production_animated_h
            reference_f8_skin_bind_acc += weight * reference_skin_bind_h
            reference_f8_qbone_acc += weight * reference_f8_qbone_h
            reference_f8_animated_acc += weight * reference_f8_animated_h
            reference_f8_weighted_acc += weight * reference_f8_final_h
            reference_f9_qbone_acc += weight * reference_f9_qbone_h
            reference_f9_animated_acc += weight * reference_f9_animated_h
            reference_f9_weighted_acc += weight * reference_f9_final_h
            for fname in _SKIN_3G_FORMULAS:
                mat = _skin_3g_matrix_for_formula(
                    fname, skin_bind, animated_world, q_tr_inv, q_rt_inv,
                    q_tr_direct, q_rt_direct,
                    rot_only_skin_bind=skin_bind_rot_only,
                    xoreos_first_frame_outer=xoreos_first_frame_outer,
                )
                formula_acc[fname] += weight * (mat @ hv)
            if uploaded_palette_arr is not None and 0 <= local_idx < len(uploaded_palette_arr):
                gpu_acc += weight * (np.asarray(uploaded_palette_arr[local_idx], dtype=np.float64) @ hv_vbo)
            per_bone_production = []
            if uploaded_palette_arr is not None and 0 <= local_idx < len(uploaded_palette_arr):
                try:
                    prod_h = np.asarray(uploaded_palette_arr[local_idx], dtype=np.float64) @ hv_vbo
                    prod_pos = prod_h[:3] / (prod_h[3] if abs(prod_h[3]) > 1e-9 else 1.0)
                    per_bone_production = [round(float(v), 6) for v in prod_pos]
                except Exception:
                    per_bone_production = []
            influence_records.append({
                'local_bone_index': local_idx,
                'bone_name': bone_name,
                'weight': round(weight, 6),
                'parent_chain': _node_parent_chain_names(bone_node),
                'animated_world_chain': _node_pose_chain_records(bone_node, anim_pose),
                'animated_local': _pose_node_transform(anim_pose, bone_node) if bone_node is not None else {},
                'animated_world_matrix': _matrix4_json(animated_world),
                'qbone_tbone_TR_matrix': _matrix4_json(q_tr_direct),
                'qbone_tbone_RT_matrix': _matrix4_json(q_rt_direct),
                'qbone_tbone_TR_inverse_matrix': _matrix4_json(q_tr_inv),
                'qbone_tbone_RT_inverse_matrix': _matrix4_json(q_rt_inv),
                'production_per_bone_position_from_vbo_in_pos': per_bone_production,
                'production_replay_pre_weight_position': _homogeneous_position_json(production_animated_h),
                'reference_f8_replay_pre_weight_position': _homogeneous_position_json(reference_f8_final_h),
                'reference_f9_replay_pre_weight_position': _homogeneous_position_json(reference_f9_final_h),
                'skin_bind_applied_position': _homogeneous_position_json(reference_skin_bind_h),
                'skin_unbind_applied_position_f8': _homogeneous_position_json(reference_f8_final_h),
                'skin_unbind_applied_position_f9': _homogeneous_position_json(reference_f9_final_h),
                'production_qbone_applied_position': _homogeneous_position_json(production_qbone_h),
                'reference_f8_qbone_applied_position': _homogeneous_position_json(reference_f8_qbone_h),
                'reference_f9_qbone_applied_position': _homogeneous_position_json(reference_f9_qbone_h),
                'animated_world_applied_position': _homogeneous_position_json(production_animated_h),
                'reference_f8_animated_world_applied_position': _homogeneous_position_json(reference_f8_animated_h),
                'reference_f9_animated_world_applied_position': _homogeneous_position_json(reference_f9_animated_h),
            })
        candidate_positions = {}
        candidate_distances = {}
        raw_space_positions = {
            'H1_raw_as_mesh_space': {},
            'H2_raw_as_skin_node_local': {},
        }
        raw_space_distances = {
            'H1_raw_as_mesh_space': {},
            'H2_raw_as_skin_node_local': {},
        }
        hv_skin_local = skin_bind @ hv
        for fname, accum in formula_acc.items():
            pos = accum[:3] / (accum[3] if abs(accum[3]) > 1e-9 else 1.0)
            candidate_positions[fname] = [round(float(v), 6) for v in pos]
            candidate_distances[fname] = round(float(np.linalg.norm(pos - raw)), 6)
            raw_space_positions['H1_raw_as_mesh_space'][fname] = candidate_positions[fname]
            raw_space_distances['H1_raw_as_mesh_space'][fname] = candidate_distances[fname]

            h2_accum = np.zeros(4, dtype=np.float64)
            for inf in influences:
                local_idx = int(getattr(inf, 'bone_index', 0) or 0)
                weight = float(getattr(inf, 'weight', 0.0) or 0.0)
                bone_name = bone_map[local_idx] if 0 <= local_idx < len(bone_map) else ''
                bone_node = lookup.get(str(bone_name).lower()) if bone_name else None
                animated_world = _node_world_matrix_for_pose_np(bone_node, anim_pose, {})
                q_tr_inv = _qbone_matrix_np(node, local_idx, order='TR', inverse=True)
                q_rt_inv = _qbone_matrix_np(node, local_idx, order='RT', inverse=True)
                q_tr_direct = _qbone_matrix_np(node, local_idx, order='TR', inverse=False)
                q_rt_direct = _qbone_matrix_np(node, local_idx, order='RT', inverse=False)
                mat = _skin_3g_matrix_for_formula(
                    fname, skin_bind, animated_world, q_tr_inv, q_rt_inv,
                    q_tr_direct, q_rt_direct,
                    rot_only_skin_bind=skin_bind_rot_only,
                    xoreos_first_frame_outer=xoreos_first_frame_outer,
                )
                h2_accum += weight * (mat @ hv_skin_local)
            h2_pos = h2_accum[:3] / (h2_accum[3] if abs(h2_accum[3]) > 1e-9 else 1.0)
            raw_space_positions['H2_raw_as_skin_node_local'][fname] = [
                round(float(v), 6) for v in h2_pos
            ]
            raw_space_distances['H2_raw_as_skin_node_local'][fname] = round(
                float(np.linalg.norm(h2_pos - raw)), 6)
        gpu_pos = gpu_acc[:3] / (gpu_acc[3] if abs(gpu_acc[3]) > 1e-9 else 1.0)
        weight_total = sum(float(getattr(inf, 'weight', 0.0) or 0.0) for inf in influences)
        weighted_vbo_h = hv_vbo * weight_total
        raw_skin_bind_h = skin_bind @ hv_vbo
        raw_skin_unbind_h = inv_skin_bind @ hv_vbo
        first_divergence_f8 = _first_divergence_stage([
            ('raw_to_vbo', raw, vbo),
            ('skin_bind_applied', weighted_vbo_h, reference_f8_skin_bind_acc),
            ('qbone_inverse_applied', production_qbone_acc, reference_f8_qbone_acc),
            ('animated_world_applied', production_weighted_acc, reference_f8_animated_acc),
            ('skin_unbind_applied', production_weighted_acc, reference_f8_weighted_acc),
        ])
        first_divergence_f9 = _first_divergence_stage([
            ('raw_to_vbo', raw, vbo),
            ('skin_bind_applied', weighted_vbo_h, reference_f8_skin_bind_acc),
            ('qbone_direct_applied', production_qbone_acc, reference_f9_qbone_acc),
            ('animated_world_applied', production_weighted_acc, reference_f9_animated_acc),
            ('skin_unbind_applied', production_weighted_acc, reference_f9_weighted_acc),
        ])
        first_post_skin_bind_f8 = _first_divergence_stage([
            ('qbone_inverse_after_skin_bind', production_qbone_acc, reference_f8_qbone_acc),
            ('animated_world_after_skin_bind', production_weighted_acc, reference_f8_animated_acc),
            ('skin_unbind_after_animated_world', production_weighted_acc, reference_f8_weighted_acc),
        ])
        first_post_skin_bind_f9 = _first_divergence_stage([
            ('qbone_direct_after_skin_bind', production_qbone_acc, reference_f9_qbone_acc),
            ('animated_world_after_skin_bind', production_weighted_acc, reference_f9_animated_acc),
            ('skin_unbind_after_animated_world', production_weighted_acc, reference_f9_weighted_acc),
        ])
        try:
            skin_bind_delta = float(np.max(np.abs((raw_skin_bind_h[:3] / raw_skin_bind_h[3]) - vbo)))
        except Exception:
            skin_bind_delta = None
        try:
            skin_unbind_delta = float(np.max(np.abs((raw_skin_unbind_h[:3] / raw_skin_unbind_h[3]) - vbo)))
        except Exception:
            skin_unbind_delta = None

        # ── 3i Step 6: pre-qBone basis provenance ───────────────────────────
        # Decisive question: does GhostRigger already pre-apply some basis
        # change to the raw MDX position before qBone/tBone is multiplied?
        #
        # The loader (src/core/kotor_loader.py:_read_mesh L666-677) writes
        # ``gr.vertices = raw_verts`` directly from PyKotor's
        # ``mesh.vertex_positions``.  No bind matrix is ever folded in, so
        # the VBO is the raw MDX position basis (= xoreos's
        # ``_initialVertexCoords``).  ``raw_vs_vbo_max_abs == 0.0`` proven in
        # Step 1 confirms this.  Together these say the loader does NOT
        # pre-bake ``inverse(node->_invBindPose)`` into the input.
        #
        # On the reference side, xoreos's pre-wrapper ``transform`` is
        # ``inverse(_invBindPose)`` where ``_invBindPose`` is built by
        # rotating in the first-frame orientation of every parent in the
        # node chain (xoreos ModelNode::computeInverseBindPose L891-919).
        # Position frames are read at L904-907 but never applied, so the
        # reference outer matrix is rotation-only.
        #
        # GhostRigger's ``skin_bind`` is the full position+rotation node
        # world matrix from ``_node_world_matrix_for_pose_np(skin_node, None,
        # {})``.  When a translation is present it makes the wrapper apply a
        # structurally different transform than xoreos does.  The fields
        # below quantify that mismatch per probe, and a rotation-only stand-
        # in is reported so reduction can decide whether the residual error
        # is purely the translation column or whether qBone/tBone itself was
        # imported in a different basis.
        skin_bind_translation_norm = _matrix_translation_norm(skin_bind)
        skin_bind_rot_only = _matrix_rotation_only(skin_bind)
        rot_only_h = (skin_bind_rot_only @ hv_vbo) if skin_bind_rot_only is not None else None
        try:
            rot_only_delta = (
                None if rot_only_h is None
                else round(float(np.max(np.abs((rot_only_h[:3] / rot_only_h[3]) - vbo))), 6)
            )
        except Exception:
            rot_only_delta = None
        try:
            inv_skin_bind_times_vbo_h = inv_skin_bind @ hv_vbo
            inv_skin_bind_vs_raw_max_abs = round(float(np.max(np.abs(
                (inv_skin_bind_times_vbo_h[:3] / inv_skin_bind_times_vbo_h[3]) - raw))), 6)
        except Exception:
            inv_skin_bind_times_vbo_h = None
            inv_skin_bind_vs_raw_max_abs = None
        # Loader pre-transform classification: "none_passthrough" is the
        # only outcome consistent with the loader source AND with raw==vbo.
        loader_pretransform = (
            'none_passthrough'
            if abs(float(np.max(np.abs(vbo - raw)))) <= 1e-9
            else 'pretransform_detected'
        )
        # If the loader had pre-applied skin_bind, then inv(skin_bind)*vbo
        # would equal raw.  If not, inv(skin_bind)*vbo will diverge by
        # exactly the amount of skin_bind's effect.  Empty/identity
        # skin_bind makes both checks degenerate.
        inverse_skin_bind_check = (
            'no_pretransform_loader_passthrough'
            if (inv_skin_bind_vs_raw_max_abs is None
                or inv_skin_bind_vs_raw_max_abs > 1e-6)
            else 'identity_skin_bind_or_pretransform_indistinguishable'
        )
        pre_qbone_basis_provenance = {
            'loader_pretransform_detected': loader_pretransform,
            'loader_source': (
                'src/core/kotor_loader.py:_read_mesh L666-677 stores PyKotor '
                'mesh.vertex_positions directly into gr.vertices (no bind '
                'transform)'
            ),
            'loader_vbo_source': (
                'src/gui/gpu_renderer.py uploads gr.vertices verbatim into '
                'pos VBO via _GpuMesh.uploaded_positions'
            ),
            'reference_initial_vertex_coords_source': (
                'xoreos Animation::updateSkinnedModel uses '
                'node._initialVertexCoords (raw MDX) before applying '
                'transform'
            ),
            'reference_pre_wrapper_transform_composition': (
                'rotation_only_chain_of_first_frame_orientations'
            ),
            'reference_pre_wrapper_transform_source': (
                'xoreos ModelNode::computeInverseBindPose L891-919 '
                '(_positionFrames read at L904-907 but never applied; '
                'orientations rotated in via glm::rotate at L912)'
            ),
            'ghostrigger_skin_bind_composition': (
                'position_plus_rotation_node_world_pose_matrix'
            ),
            'ghostrigger_skin_bind_source': (
                'gpu_skinning.MatrixPaletteUploader._skin_bind_matrix from '
                '_node_world_matrix_for_pose_np(skin_node, None, {})'
            ),
            'skin_bind_translation_norm': skin_bind_translation_norm,
            'skin_bind_rotation_only_matrix': _matrix4_json(skin_bind_rot_only),
            'reference_pre_qbone_with_full_skin_bind_position':
                _homogeneous_position_json(raw_skin_bind_h),
            'reference_pre_qbone_with_rotation_only_skin_bind_position':
                _homogeneous_position_json(rot_only_h),
            'reference_pre_qbone_with_rotation_only_vs_production_vbo_max_abs':
                rot_only_delta,
            'inverse_skin_bind_times_vbo_position':
                _homogeneous_position_json(inv_skin_bind_times_vbo_h),
            'inverse_skin_bind_times_vbo_vs_raw_max_abs':
                inv_skin_bind_vs_raw_max_abs,
            'inverse_skin_bind_check': inverse_skin_bind_check,
        }

        # ── 3i Step 7: B-translation diagnostic comparison ───────────────────
        # F11 (rotation-only skin_bind wrapper) and F12 (xoreos-strict
        # first-frame-orientation chain wrapper) are both new diagnostic
        # candidates added to ``_SKIN_3G_FORMULAS``.  Their accumulated
        # weighted positions live in ``formula_acc`` already; we surface
        # them explicitly here alongside a |F11 - F1| / |F12 - F1| delta
        # and a "collapses to production" boolean so the audit doc and
        # reduction script can name the outcome without re-deriving it.
        f11_acc = formula_acc.get('F11_rotation_only_skin_bind_wrapper')
        f12_acc = formula_acc.get('F12_xoreos_first_frame_orientation_wrapper')
        f1_acc = formula_acc.get('F1_current_TR_inverse')

        def _norm_pos(acc):
            try:
                if acc is None:
                    return None
                w = float(acc[3]) if abs(float(acc[3])) > 1e-9 else 1.0
                return acc[:3] / w
            except Exception:
                return None

        f1_pos = _norm_pos(f1_acc)
        f11_pos = _norm_pos(f11_acc)
        f12_pos = _norm_pos(f12_acc)

        def _delta_to_production(pos):
            if pos is None or f1_pos is None:
                return None
            try:
                return round(float(np.max(np.abs(pos - f1_pos))), 6)
            except Exception:
                return None

        f11_vs_f1 = _delta_to_production(f11_pos)
        f12_vs_f1 = _delta_to_production(f12_pos)
        f11_collapses = (f11_vs_f1 is not None and f11_vs_f1 < 1e-4)
        f12_collapses = (f12_vs_f1 is not None and f12_vs_f1 < 1e-4)
        # Per-probe interpretation: matches Step 7 stop/go phrasing.
        if f11_collapses and f12_collapses:
            step7_interpretation = (
                'b_translation_loose_and_strict_both_collapse_to_production'
            )
        elif f11_collapses and not f12_collapses:
            step7_interpretation = (
                'b_translation_loose_collapses_to_production_strict_diverges'
            )
        elif not f11_collapses and f12_collapses:
            step7_interpretation = (
                'b_translation_loose_diverges_strict_collapses_to_production'
            )
        else:
            step7_interpretation = (
                'b_translation_loose_and_strict_both_diverge_from_production'
            )
        step7_b_translation_probe = {
            'f11_outer_composition': 'rotation_only_skin_bind',
            'f12_outer_composition': (
                'xoreos_first_frame_orientation_chain_M_chain'
            ),
            'f11_outer_matrix': _matrix4_json(skin_bind_rot_only),
            'f12_outer_matrix': _matrix4_json(xoreos_first_frame_outer),
            'f11_weighted_position': (
                [round(float(v), 6) for v in f11_pos] if f11_pos is not None else []
            ),
            'f12_weighted_position': (
                [round(float(v), 6) for v in f12_pos] if f12_pos is not None else []
            ),
            'production_weighted_position': (
                [round(float(v), 6) for v in f1_pos] if f1_pos is not None else []
            ),
            'f11_vs_production_max_abs': f11_vs_f1,
            'f12_vs_production_max_abs': f12_vs_f1,
            'f11_collapses_to_production': bool(f11_collapses),
            'f12_collapses_to_production': bool(f12_collapses),
            'step7_interpretation': step7_interpretation,
        }

        out.append({
            **probe,
            'raw_position': [round(float(v), 6) for v in raw],
            'raw_mdx_position': [round(float(v), 6) for v in raw],
            'vbo_in_pos': [round(float(v), 6) for v in vbo],
            'vbo_row_index': int(vbo_row_index),
            'vbo_source_vertex_index': (
                int(uploaded_source_indices[vbo_row_index])
                if uploaded_source_indices is not None and 0 <= vbo_row_index < len(uploaded_source_indices)
                else vi
            ),
            'raw_vs_vbo_delta': [round(float(vbo[i] - raw[i]), 6) for i in range(3)],
            'raw_vs_vbo_max_abs': round(float(np.max(np.abs(vbo - raw))), 6),
            'interpreted_raw_space': 'skin_node_vbo_input_space',
            'skin_node_bind_position': _pose_node_transform(None, node).get('position', []),
            'skin_node_bind_rotation_quat': _pose_node_transform(None, node).get('rotation', []),
            'skin_node_bind_matrix': _matrix4_json(skin_bind),
            'skin_node_pose_matrix': _matrix4_json(skin_pose),
            'bone_ids': [int(getattr(inf, 'bone_index', 0) or 0) for inf in influences],
            'weights': [round(float(getattr(inf, 'weight', 0.0) or 0.0), 6) for inf in influences],
            'vbo_bone_ids': uploaded_bone_ids[vbo_row_index] if uploaded_bone_ids is not None and 0 <= vbo_row_index < len(uploaded_bone_ids) else [],
            'vbo_weights': uploaded_weights[vbo_row_index] if uploaded_weights is not None and 0 <= vbo_row_index < len(uploaded_weights) else [],
            'influences': influence_records,
            'production_replay_pre_weight_positions': [
                rec.get('production_replay_pre_weight_position', [])
                for rec in influence_records
            ],
            'reference_f8_replay_pre_weight_positions': [
                rec.get('reference_f8_replay_pre_weight_position', [])
                for rec in influence_records
            ],
            'reference_f9_replay_pre_weight_positions': [
                rec.get('reference_f9_replay_pre_weight_position', [])
                for rec in influence_records
            ],
            'production_weighted_sum_position': _homogeneous_position_json(production_weighted_acc),
            'reference_f8_weighted_sum_position': _homogeneous_position_json(reference_f8_weighted_acc),
            'reference_f9_weighted_sum_position': _homogeneous_position_json(reference_f9_weighted_acc),
            'qbone_already_raw_basis_probe_weighted_sum_position': _homogeneous_position_json(production_weighted_acc),
            'qbone_after_skin_bind_probe_weighted_sum_position_f8': _homogeneous_position_json(reference_f8_weighted_acc),
            'qbone_after_skin_bind_probe_weighted_sum_position_f9': _homogeneous_position_json(reference_f9_weighted_acc),
            'raw_after_skin_bind_position': _homogeneous_position_json(raw_skin_bind_h),
            'raw_after_skin_unbind_position': _homogeneous_position_json(raw_skin_unbind_h),
            'reference_pre_qbone_input_position': _homogeneous_position_json(raw_skin_bind_h),
            'reference_pre_qbone_input_source': 'xoreos transform * initialVertexCoords; Three.js bindMatrix * position',
            'production_pre_qbone_input_position': [round(float(v), 6) for v in vbo],
            'reference_pre_qbone_vs_production_vbo_max_abs': (
                round(skin_bind_delta, 6) if skin_bind_delta is not None else None
            ),
            'skin_bind_moves_raw_max_abs': round(skin_bind_delta, 6) if skin_bind_delta is not None else None,
            'skin_unbind_moves_raw_max_abs': round(skin_unbind_delta, 6) if skin_unbind_delta is not None else None,
            'skin_bind_applied_position': _homogeneous_position_json(reference_f8_skin_bind_acc),
            'skin_unbind_applied_position': _homogeneous_position_json(reference_f8_weighted_acc),
            'animated_world_applied_position': _homogeneous_position_json(production_weighted_acc),
            'first_divergence_stage': first_divergence_f8,
            'first_divergence_stage_reference_f8': first_divergence_f8,
            'first_divergence_stage_reference_f9': first_divergence_f9,
            'first_post_skin_bind_mismatch_stage_reference_f8': first_post_skin_bind_f8,
            'first_post_skin_bind_mismatch_stage_reference_f9': first_post_skin_bind_f9,
            'pre_qbone_basis_provenance': pre_qbone_basis_provenance,
            'step7_b_translation': step7_b_translation_probe,
            'candidate_formula_positions': candidate_positions,
            'candidate_distance_from_raw': candidate_distances,
            'raw_vertex_space_candidate_positions': raw_space_positions,
            'raw_vertex_space_distance_from_raw': raw_space_distances,
            'gpu_skinned_actual': [round(float(v), 6) for v in gpu_pos],
            'gpu_skinned_position_after_3g_fix': [round(float(v), 6) for v in gpu_pos],
            'gpu_skinned_actual_method': 'weighted uploaded_u_bones decode',
        })
    return out


def _skin_live_slot_records(
        *,
        model,
        node,
        bone_map: List[str],
        skin_data: List[object],
        bone_remap: Optional[Dict[int, int]],
        uploader,
        palette_arr,
        uploaded_palette_arr,
        anim_pose,
        anim_base_pose) -> List[dict]:
    live: Dict[int, dict] = {}
    for vi, skin in enumerate(skin_data):
        influences = list(getattr(skin, 'influences', []) or [])
        for inf in influences:
            weight = float(getattr(inf, 'weight', 0.0) or 0.0)
            if weight < 0.0001:
                continue
            local_idx = int(getattr(inf, 'bone_index', 0) or 0)
            slot = live.setdefault(local_idx, {
                'local_bone_index': local_idx,
                'vertex_count': 0,
                'weight_sum': 0.0,
                'max_weight': 0.0,
                'first_vertex': vi,
            })
            slot['vertex_count'] += 1
            slot['weight_sum'] += weight
            slot['max_weight'] = max(slot['max_weight'], weight)

    root_name = str(getattr(getattr(model, 'root_node', None), 'name', '') or
                    getattr(model, 'name', '') or '')
    records = []
    inv_source = {}
    if uploader is not None:
        inv_source = getattr(uploader, '_inv_bind_anim', None) or getattr(uploader, '_inv_bind', {})
        if not isinstance(inv_source, dict):
            inv_source = {}

    for local_idx in sorted(live):
        bone_name = bone_map[local_idx] if 0 <= local_idx < len(bone_map) else ''
        palette_idx = bone_remap.get(local_idx, 0) if bone_remap is not None else local_idx
        bone_node = None
        try:
            bone_node = model.find_node(bone_name) if bone_name else None
        except Exception:
            bone_node = None
        local_inv_source = getattr(uploader, '_skin_local_inv_bind_by_slot', {}) if uploader is not None else {}
        inv_bind = local_inv_source.get(local_idx) if isinstance(local_inv_source, dict) else None
        if inv_bind is None:
            inv_bind = inv_source.get(str(bone_name).lower()) if bone_name else None
        cpu_matrix = None
        if palette_arr is not None and 0 <= palette_idx < len(palette_arr):
            cpu_matrix = palette_arr[palette_idx].tolist()
        uploaded_matrix = None
        if uploaded_palette_arr is not None and 0 <= palette_idx < len(uploaded_palette_arr):
            uploaded_matrix = uploaded_palette_arr[palette_idx].tolist()
        parity_error = None
        if cpu_matrix is not None and uploaded_matrix is not None and _NUMPY:
            try:
                parity_error = float(np.max(np.abs(
                    np.asarray(cpu_matrix, dtype=np.float64) -
                    np.asarray(uploaded_matrix, dtype=np.float64))))
            except Exception:
                parity_error = None
        qbone_inv = _qbone_inverse_bind_json(node, local_idx)
        qbone_direct = _qbone_direct_bind_json(node, local_idx)
        qbone_error = None
        if inv_bind is not None and qbone_inv and _NUMPY:
            try:
                qbone_error = float(np.max(np.abs(
                    np.asarray(inv_bind, dtype=np.float64) -
                    np.asarray(qbone_inv, dtype=np.float64))))
            except Exception:
                qbone_error = None
        slot = live[local_idx]
        records.append({
            'local_bone_index': local_idx,
            'bone_name': bone_name,
            'is_empty_bone_name': bone_name == '',
            'is_model_root': bool(bone_name and root_name and bone_name.lower() == root_name.lower()),
            'palette_index': int(palette_idx),
            'vertex_count': int(slot['vertex_count']),
            'weight_sum': round(float(slot['weight_sum']), 6),
            'max_weight': round(float(slot['max_weight']), 6),
            'first_vertex': int(slot['first_vertex']),
            'bind_local': _pose_node_transform(None, bone_node) if bone_node is not None else {},
            'base_pose_local': _pose_node_transform(anim_base_pose, bone_node) if bone_node is not None else {},
            'animated_local': _pose_node_transform(anim_pose, bone_node) if bone_node is not None else {},
            'inverse_bind_matrix': _matrix4_json(inv_bind),
            'qbone_inverse_bind_matrix': qbone_inv,
            'qbone_tbone_direct_matrix': qbone_direct,
            'bone_inverse_bind_source': getattr(uploader, '_skin_inverse_bind_source', '')
                                      if uploader is not None else '',
            'inverse_bind_vs_qbone_max_abs': qbone_error,
            'cpu_composed_skinning_matrix': _matrix4_json(cpu_matrix),
            'uploaded_u_bones_matrix': _matrix4_json(uploaded_matrix),
            'cpu_vs_uploaded_max_abs': parity_error,
        })
    return records


def _build_skin_dump_record(
        *,
        model,
        node,
        pass_name: str,
        uploader,
        bone_remap: Optional[Dict[int, int]],
        uniforms: Dict[str, object],
        gm=None,
        anim_pose,
        anim_base_pose,
        anim_time: float,
        selected_vertex: Optional[int] = None) -> dict:
    """Build one skinning parity diagnostic record for a skin draw."""
    bone_map = list(getattr(node, 'bone_map', []) or [])
    skin_data = list(getattr(node, 'skin_data', []) or [])
    vertices = list(getattr(node, 'vertices', getattr(node, 'verts', [])) or [])
    vertex_index = selected_vertex if selected_vertex is not None else _select_skin_probe_vertex(node)
    vertex_index = max(0, min(int(vertex_index), max(0, len(vertices) - 1)))
    skin = skin_data[vertex_index] if vertex_index < len(skin_data) else None
    influences = list(getattr(skin, 'influences', []) or []) if skin is not None else []

    palette_arr = None
    try:
        palette_arr = uploader.as_numpy_array() if uploader is not None else None
    except Exception:
        palette_arr = None
    uploaded_palette_arr = _uploaded_palette_array_from_uploader(uploader)

    referenced = []
    for inf in influences[:4]:
        local_idx = int(getattr(inf, 'bone_index', 0) or 0)
        weight = float(getattr(inf, 'weight', 0.0) or 0.0)
        bone_name = bone_map[local_idx] if 0 <= local_idx < len(bone_map) else ''
        palette_idx = bone_remap.get(local_idx, 0) if bone_remap is not None else local_idx
        bone_node = None
        try:
            bone_node = model.find_node(bone_name) if bone_name else None
        except Exception:
            bone_node = None
        inv_bind = None
        if uploader is not None:
            local_inv_source = getattr(uploader, '_skin_local_inv_bind_by_slot', {})
            if isinstance(local_inv_source, dict):
                inv_bind = local_inv_source.get(local_idx)
            inv_source = getattr(uploader, '_inv_bind_anim', None) or getattr(uploader, '_inv_bind', {})
            if inv_bind is None:
                inv_bind = inv_source.get(str(bone_name).lower()) if isinstance(inv_source, dict) else None
        uploaded = None
        if palette_arr is not None and 0 <= palette_idx < len(palette_arr):
            uploaded = palette_arr[palette_idx].tolist()
        bind_world = _matrix4_inverse_json(inv_bind)
        referenced.append({
            'local_bone_index': local_idx,
            'weight': weight,
            'bone_name': bone_name,
            'palette_index': int(palette_idx),
            'bind_local': _pose_node_transform(None, bone_node) if bone_node is not None else {},
            'base_pose_local': _pose_node_transform(anim_base_pose, bone_node) if bone_node is not None else {},
            'animated_local': _pose_node_transform(anim_pose, bone_node) if bone_node is not None else {},
            'bind_pose_world_matrix': bind_world,
            'animated_world_matrix': _matrix4_mul_json(uploaded, bind_world),
            'inverse_bind_matrix': _matrix4_json(inv_bind),
            'composed_skinning_matrix': _matrix4_json(uploaded),
            'uploaded_u_bones_matrix': _matrix4_json(uploaded),
        })

    remap_items = sorted((int(k), int(v)) for k, v in (bone_remap or {}).items())
    referenced_local = [int(getattr(inf, 'bone_index', 0) or 0) for inf in influences[:4]]
    live_slots = _skin_live_slot_records(
        model=model,
        node=node,
        bone_map=bone_map,
        skin_data=skin_data,
        bone_remap=bone_remap,
        uploader=uploader,
        palette_arr=palette_arr,
        uploaded_palette_arr=uploaded_palette_arr,
        anim_pose=anim_pose,
        anim_base_pose=anim_base_pose,
    )
    convention_probes = _skin_3g_candidate_records(
        model=model,
        node=node,
        bone_map=bone_map,
        skin_data=skin_data,
        vertices=vertices,
        anim_pose=anim_pose,
        uploaded_palette_arr=uploaded_palette_arr,
        uploaded_positions=getattr(gm, 'uploaded_positions', None) if gm is not None else None,
        uploaded_bone_ids=getattr(gm, 'uploaded_bone_ids', None) if gm is not None else None,
        uploaded_weights=getattr(gm, 'uploaded_weights', None) if gm is not None else None,
        uploaded_source_indices=getattr(gm, 'uploaded_source_indices', None) if gm is not None else None,
    )
    skin_bind_matrix = getattr(uploader, '_skin_bind_matrix', None) if uploader is not None else None
    first_live = live_slots[0] if live_slots else {}

    # ── 3i Step 6: aggregate pre-qBone basis provenance summary ─────────
    # Roll the per-probe provenance up so the audit doc can read a single
    # classification line per skin draw.  The classification follows the
    # decision rule in the user's Step 6 brief:
    #   Outcome A: GhostRigger raw/VBO already pre-bound  → keep 3f, document
    #              wrapper as semantically wrong for our representation.
    #   Outcome B: GhostRigger raw/VBO not pre-bound, but qBone/tBone
    #              imported assuming a different basis → fix in loader/qBone
    #              import semantics, not palette multiplication.
    # The loader source (kotor_loader.py:_read_mesh L666-677 → gr.vertices =
    # raw_verts) and ``raw_vs_vbo_max_abs == 0.0`` together force the
    # pretransform branch to "none_passthrough" whenever the loader path is
    # observed; the only remaining axis is whether skin_bind carries
    # translation that xoreos's rotation-only transform does not.
    skin_bind_translation_norm_top = _matrix_translation_norm(skin_bind_matrix)
    probes_have_pretransform = any(
        (p.get('pre_qbone_basis_provenance') or {}).get('loader_pretransform_detected')
            == 'pretransform_detected'
        for p in convention_probes
    )
    if convention_probes:
        loader_pretransform_summary = (
            'pretransform_detected_per_probe'
            if probes_have_pretransform else 'none_passthrough_proven_by_raw_equals_vbo'
        )
    else:
        loader_pretransform_summary = 'no_probes_available'
    if skin_bind_translation_norm_top is None:
        skin_bind_includes_translation = None
        classification = 'unavailable_skin_bind_missing'
    elif skin_bind_translation_norm_top > 1e-6:
        skin_bind_includes_translation = True
        classification = (
            'outcome_b_loader_passthrough_but_skin_bind_includes_translation'
            '_xoreos_transform_does_not'
        )
    else:
        skin_bind_includes_translation = False
        classification = (
            'outcome_b_candidate_no_translation_in_skin_bind_check_qbone_basis'
        )
    # ── 3i Step 7: aggregate B-translation diagnostic across probes ─────
    step7_probes = [
        (p.get('step7_b_translation') or {})
        for p in convention_probes
    ]
    f11_collapse_flags = [bool(p.get('f11_collapses_to_production'))
                          for p in step7_probes if p]
    f12_collapse_flags = [bool(p.get('f12_collapses_to_production'))
                          for p in step7_probes if p]
    f11_vs_f1_values = [
        p.get('f11_vs_production_max_abs') for p in step7_probes
        if p and p.get('f11_vs_production_max_abs') is not None
    ]
    f12_vs_f1_values = [
        p.get('f12_vs_production_max_abs') for p in step7_probes
        if p and p.get('f12_vs_production_max_abs') is not None
    ]
    if not step7_probes:
        step7_summary_classification = 'no_probes_available'
    elif all(f11_collapse_flags) and all(f12_collapse_flags):
        step7_summary_classification = (
            'b_translation_loose_and_strict_both_collapse_to_production'
            '_no_visual_change_expected'
        )
    elif all(f11_collapse_flags) and not all(f12_collapse_flags):
        step7_summary_classification = (
            'b_translation_loose_collapses_to_production_strict_diverges'
            '_strict_visual_gate_warranted'
        )
    elif not all(f11_collapse_flags) and all(f12_collapse_flags):
        step7_summary_classification = (
            'b_translation_loose_diverges_strict_collapses_to_production'
            '_loose_visual_gate_warranted'
        )
    else:
        step7_summary_classification = (
            'b_translation_loose_and_strict_both_diverge_from_production'
            '_either_variant_visual_gate_warranted'
        )
    step7_b_translation_summary = {
        'f11_outer_composition': 'rotation_only_skin_bind',
        'f12_outer_composition': (
            'xoreos_first_frame_orientation_chain_M_chain'
        ),
        'f12_outer_source': (
            'xoreos ModelNode::computeInverseBindPose L891-919: '
            'transform = inverse(_invBindPose) where _invBindPose is the '
            'composed first-frame orientation chain from skin_node parents'
        ),
        'probes_total': len(step7_probes),
        'probes_with_f11_data': sum(1 for p in step7_probes if p),
        'f11_collapses_to_production_in_all_probes': (
            bool(f11_collapse_flags) and all(f11_collapse_flags)
        ),
        'f12_collapses_to_production_in_all_probes': (
            bool(f12_collapse_flags) and all(f12_collapse_flags)
        ),
        'f11_vs_production_max_max_abs': (
            round(max(f11_vs_f1_values), 6) if f11_vs_f1_values else None
        ),
        'f12_vs_production_max_max_abs': (
            round(max(f12_vs_f1_values), 6) if f12_vs_f1_values else None
        ),
        'classification': step7_summary_classification,
        'visual_gate_recommendation': (
            'No visual gate needed: both diagnostic variants produce '
            'pixel-identical output to current 3f production. The '
            'B-translation hypothesis is provably a no-op for this skin '
            'draw. Pivot to 3i B-qbone-basis (qBone/tBone import semantics).'
            if step7_summary_classification.startswith(
                'b_translation_loose_and_strict_both_collapse'
            )
            else (
                'Visual gate warranted: at least one diagnostic variant '
                'produces a different result than current 3f production. '
                'Capture before/after screenshots for c_drexlf, c_brith, '
                'and c_bomabeast under the divergent variant before any '
                'production change.'
            )
        ),
    }

    pre_qbone_basis_provenance_summary = {
        'loader_pretransform': loader_pretransform_summary,
        'loader_source': (
            'src/core/kotor_loader.py:_read_mesh L666-677: gr.vertices = '
            'raw_verts (PyKotor mesh.vertex_positions copy, no bind '
            'transform applied)'
        ),
        'reference_initial_vertex_coords_source': (
            'xoreos Animation::updateSkinnedModel uses '
            'node._initialVertexCoords (raw MDX) as the input to the '
            'wrapper transform'
        ),
        'reference_pre_wrapper_transform_composition': (
            'rotation_only_chain_of_first_frame_orientations'
        ),
        'reference_pre_wrapper_transform_source': (
            'xoreos ModelNode::computeInverseBindPose L891-919: position '
            'frames read at L904-907 but never applied; orientations '
            'rotated in via glm::rotate at L912; result inverted at L918'
        ),
        'ghostrigger_skin_bind_composition': (
            'position_plus_rotation_node_world_pose_matrix'
        ),
        'ghostrigger_skin_bind_source': (
            'gpu_skinning.MatrixPaletteUploader._skin_bind_matrix from '
            '_node_world_matrix_for_pose_np(skin_node, None, {})'
        ),
        'skin_bind_translation_norm': skin_bind_translation_norm_top,
        'skin_bind_includes_translation_xoreos_does_not':
            skin_bind_includes_translation,
        'classification': classification,
        'recommended_next_audit': (
            'Test rotation-only-skin_bind wrapper variant against the same '
            'tagged probes.  If reference_pre_qbone_with_rotation_only_'
            'skin_bind matches the production basis, the structural defect '
            'is the translation column inside skin_bind.  If it still '
            'diverges, the qBone/tBone data itself was imported in a '
            'basis that disagrees with the reference engines.'
        ),
    }
    return {
        'event': 'skin_draw',
        'time': time.time(),
        'model': str(getattr(model, 'name', '') or ''),
        'node': str(getattr(node, 'name', '') or ''),
        'pass': pass_name,
        'anim_time': float(anim_time),
        'anim_pose_time': float(getattr(anim_pose, 'time', 0.0) or 0.0) if anim_pose is not None else None,
        'anim_base_pose_time': float(getattr(anim_base_pose, 'time', 0.0) or 0.0) if anim_base_pose is not None else None,
        'is_skin': bool(getattr(node, 'is_skin', False)),
        'is_dangly': bool(getattr(node, 'is_dangly', False)),
        'vertex_count': len(vertices),
        'skin_data_len': len(skin_data),
        'bone_map': bone_map,
        'bone_map_len': len(bone_map),
        'bone_map_duplicates': sorted({b for b in bone_map if b and bone_map.count(b) > 1}),
        'bone_map_remap': remap_items,
        'bone_map_overflow_used': len(bone_map) > 16,
        'referenced_local_indices': referenced_local,
        'referenced_oob': [i for i in referenced_local if i < 0 or i >= len(bone_map)],
        'live_local_indices': [slot['local_bone_index'] for slot in live_slots],
        'live_palette_indices': [slot['palette_index'] for slot in live_slots],
        'live_empty_bone_slots': [
            slot['local_bone_index'] for slot in live_slots if slot['is_empty_bone_name']
        ],
        'live_model_root_slots': [
            slot['local_bone_index'] for slot in live_slots if slot['is_model_root']
        ],
        'live_slots': live_slots,
        'skin_transform_formula': getattr(uploader, '_skin_palette_formula', '')
                                  if uploader is not None else '',
        'skin_species': getattr(uploader, '_skin_species', '')
                        if uploader is not None else '',
        'skin_species_profile': getattr(
            getattr(uploader, '_skin_species_profile', None), 'label', ''
        ) if uploader is not None else '',
        'skin_profile_reason': getattr(uploader, '_skin_profile_reason', '')
                               if uploader is not None else '',
        'skin_bind_present': bool(skin_bind_matrix),
        'skin_bind_det': _matrix4_det_value(skin_bind_matrix),
        'skin_bind_matrix': _matrix4_json(skin_bind_matrix),
        'skin_bind_equivalence': _skin_bind_equivalence_record(node, uploader),
        'pre_qbone_basis_provenance_summary': pre_qbone_basis_provenance_summary,
        'step7_b_translation_summary': step7_b_translation_summary,
        'bone_inverse_bind_source': getattr(uploader, '_skin_inverse_bind_source', '')
                                    if uploader is not None else '',
        'palette_matrix_preupload_first_live_slot': first_live.get('cpu_composed_skinning_matrix', []),
        'palette_matrix_uploaded_first_live_slot': first_live.get('uploaded_u_bones_matrix', []),
        'skin_transform_convention_formulas': dict(_SKIN_3G_FORMULAS),
        'skin_transform_convention_probes': convention_probes,
        'selected_vertex': {
            'index': vertex_index,
            'position': [float(v) for v in vertices[vertex_index][:3]] if vertices else [],
            'influences': [
                {
                    'local_bone_index': int(getattr(inf, 'bone_index', 0) or 0),
                    'weight': float(getattr(inf, 'weight', 0.0) or 0.0),
                }
                for inf in influences[:4]
            ],
        },
        'referenced_bones': referenced,
        'u_skin_enabled': _uniform_trace_value(uniforms, 'u_skin_enabled'),
        'u_bone_count': _uniform_trace_value(uniforms, 'u_bone_count'),
        'palette_bone_count': int(getattr(uploader, 'bone_count', 0) or 0) if uploader is not None else 0,
        'vbo_attribute_layout': _VBO_MAIN_FORMAT,
        'bone_ids_vbo_attribute_layout': _VBO_BONE_IDS_FORMAT,
        'shader_bone_ids_type': 'ivec4',
        'bone_ids_attribute_format': _VBO_BONE_IDS_FORMAT,
        'weights_attribute_format': '4f',
    }


def _gl_context_backend_candidates(os_name: Optional[str] = None) -> Tuple[str, ...]:
    """Return ModernGL standalone backend candidates for this platform."""
    override = os.environ.get(_GL_BACKEND_ENV, '').strip().lower()
    if override:
        return (override,)
    platform = os.name if os_name is None else os_name
    if platform == 'nt':
        # Windows native standalone contexts are WGL; ModernGL's default path
        # resolves correctly there.  Forcing EGL on Windows fails on common wheels.
        return ('default', 'wgl', 'egl')
    if platform == 'posix':
        # Preserve the old headless Linux preference, with default/X11 fallbacks.
        return ('egl', 'default', 'x11')
    return ('default',)


def _create_moderngl_standalone_context():
    """Create a standalone ModernGL context using platform-appropriate backends."""
    failures = []
    for backend in _gl_context_backend_candidates():
        try:
            if backend == 'default':
                return moderngl.create_standalone_context(), backend
            return moderngl.create_context(standalone=True, backend=backend), backend
        except Exception as exc:
            failures.append(f"{backend}: {exc}")
            log.debug("ModernGL backend %s failed: %s", backend, exc)
    raise RuntimeError("; ".join(failures) if failures else "no ModernGL backends attempted")

def _gr_gpu_probe(node, wp, wo, is_id_rot: bool, composite_off=None) -> None:
    """GPU-path counterpart of the CPU probe in viewport.py.

    Fires once per (model_id, node_name) for skin nodes whose name contains
    'head' when env var GHOSTRIGGER_VIEWPORT_PROBE=1 is set.  Prints the
    world_transform wp, composite offset (if any), and first-vertex data so
    we can compare CPU and GPU transforms side by side.
    """
    if not _GR_GPU_PROBE:
        return
    try:
        nl = (getattr(node, 'name', '') or '').lower()
    except Exception:
        return
    if not getattr(node, 'is_skin', False) or 'head' not in nl:
        return
    key = (id(getattr(node, '_model_ref', None)), nl, id(node))
    if key in _GR_GPU_PROBE_SEEN:
        return
    _GR_GPU_PROBE_SEEN.add(key)
    import sys as _sys
    try:
        verts = getattr(node, 'vertices', []) or []
        v0 = verts[0] if verts else (0.0, 0.0, 0.0)
        pos = tuple(round(float(x), 4) for x in getattr(node, 'position', (0,0,0)))
        wpr = tuple(round(float(x), 4) for x in wp)
        wor = tuple(round(float(x), 4) for x in wo)
        v0r = tuple(round(float(x), 4) for x in v0)
        # Include composite_offset in the expected-world so the probe matches
        # the actual rendered position after the Bug-C fix in _build_vbo_data.
        _cox = float(composite_off[0]) if composite_off is not None else 0.0
        _coy = float(composite_off[1]) if composite_off is not None else 0.0
        _coz = float(composite_off[2]) if composite_off is not None else 0.0
        ew = (float(v0[0]) + float(wp[0]) + _cox,
              float(v0[1]) + float(wp[1]) + _coy,
              float(v0[2]) + float(wp[2]) + _coz)
        co = None
        if composite_off is not None:
            co = tuple(round(float(x), 4) for x in composite_off)
        _sys.stderr.write(
            f"[GR-PROBE GPU-vbo] node={node.name} is_skin=True nvert={len(verts)}\n"
            f"  node.position       = {pos}\n"
            f"  world_transform     = wp={wpr}  wo={wor}  is_id_rot={is_id_rot}\n"
            f"  composite_offset    = {co}\n"
            f"  raw vertex[0]       = {v0r}\n"
            f"  expected world[0]   = ({ew[0]:.4f}, {ew[1]:.4f}, {ew[2]:.4f})\n"
        )
        _sys.stderr.flush()
    except Exception:
        pass

try:
    from core.qt_core.geometry.model_data import KOTOR_BASE_SKELETONS as _KOTOR_BASE_SKELETONS
except ImportError:
    try:
        from src.core.qt_core.geometry.model_data import KOTOR_BASE_SKELETONS as _KOTOR_BASE_SKELETONS
    except ImportError:
        # Fallback if model_data not importable (e.g. during testing without src on path)
        _KOTOR_BASE_SKELETONS = frozenset({
            'NULL', '', 'NONE',
            'S_FEMALE02', 'S_MALE02', 'S_FEMALE03', 'S_MALE03',
            'C_BANTHA', 'C_BRITH', 'C_DEWBACK', 'C_DURASTEEL',
            'C_KINRATH', 'C_KATH', 'C_RANCOR', 'C_WRAID', 'C_IRIAZ',
            'C_KHOUNDA', 'C_TARENTATEK', 'C_RANCORM', 'C_TUKE',
            'WARDROID', 'N_WARDROID',
        })

# ── Shared inner-geometry / face name lists ────────────────────────────────
# Imported from the single source of truth shared with viewport.py.  The GPU
# path MUST classify eye/teeth/tongue/gum/jaw nodes identically to the CPU
# rasterizer — mismatched lists caused NPC-head regressions where the CPU
# path kept inner geometry and the GPU path dropped it (or vice versa).
try:
    from core.qt_core.special.render_constants import (
        INNER_GEO_SUBSTRINGS as _INNER_GEO_SUBSTRINGS,
        FACE_MESH_SUBSTRINGS as _FACE_MESH_SUBSTRINGS,
    )
except ImportError:
    try:
        from src.core.qt_core.special.render_constants import (
            INNER_GEO_SUBSTRINGS as _INNER_GEO_SUBSTRINGS,
            FACE_MESH_SUBSTRINGS as _FACE_MESH_SUBSTRINGS,
        )
    except ImportError:
        # Last-resort fallback so the GPU path still classifies correctly even
        # when render_constants is unavailable (e.g. during import-cycle tests).
        # If you edit these values, also edit src/core/render_constants.py —
        # they MUST stay in sync with the canonical list.
        _INNER_GEO_SUBSTRINGS = (
            'eye', 'lid', 'teeth', 'tooth', 'gum', 'jaw', 'tongue',
            'teethu', 'teethl',
            'eyeball', 'cornea', 'iris', 'pupil',
            'gumskin', 'tonguemesh', 'jawskin',
            'eyelid', 'teetha', 'teethb',
        )
        _FACE_MESH_SUBSTRINGS = ('face', 'head', 'skull', 'fhead', 'fchead')

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Optional dependencies
# ─────────────────────────────────────────────────────────────────────────────

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False
    log.warning("gpu_renderer: numpy not available – GPU path disabled")

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False
    log.warning("gpu_renderer: Pillow not available")

try:
    import moderngl
    _MODERNGL = True
except ImportError:
    _MODERNGL = False
    log.info("gpu_renderer: moderngl not installed - GPU viewport rendering unavailable")

from dataclasses import dataclass, field as _field

# ── Phase A: GPU Skinning ──────────────────────────────────────────────────
# Import MatrixPaletteUploader for real-time skeletal animation in the GPU path.
# gpu_skinning.py contains the palette builder, SSBO layout, and GLSL snippets.
try:
    from core.qt_core.animation.gpu_skinning import MatrixPaletteUploader, MAX_BONES as _SKIN_MAX_BONES
    _GPU_SKINNING = True
except ImportError:
    try:
        from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader, MAX_BONES as _SKIN_MAX_BONES
        _GPU_SKINNING = True
    except ImportError:
        _GPU_SKINNING = False
        _SKIN_MAX_BONES = 128
        log.info("gpu_renderer: gpu_skinning module not available – skinning disabled")


# ─────────────────────────────────────────────────────────────────────────────
#  ModuleDrawItem — per-node render record for debug inspection
# ─────────────────────────────────────────────────────────────────────────────


__all__ = tuple(name for name in globals() if not name.startswith("__"))
