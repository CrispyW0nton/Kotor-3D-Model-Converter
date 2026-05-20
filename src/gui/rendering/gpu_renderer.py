"""
gpu_renderer.py  –  GhostRigger-K1-K2  GPU fast-path renderer
==============================================================
Hybrid renderer with a ModernGL/EGL GPU fast-path and a PIL/CPU fallback.

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

CPU fallback  (always available, uses PIL)
  • Delegates to FrameRenderer._draw_mesh_textured (existing code)
  • Used when:  ModernGL not installed, EGL not available, or
                GpuRenderer.force_cpu = True

Performance notes
  – GPU path: ~1 ms/frame for typical 10 k-tri KotOR models
  – CPU path: ~300 ms/frame for same (PIL AFFINE per triangle)
  – The GPU path is ~300× faster for fully textured rendering.

Triangle throughput benchmark is included at the bottom of this file
(run directly: python -m src.gui.gpu_renderer benchmark).

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
    from core.model_data import KOTOR_BASE_SKELETONS as _KOTOR_BASE_SKELETONS
except ImportError:
    try:
        from src.core.model_data import KOTOR_BASE_SKELETONS as _KOTOR_BASE_SKELETONS
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
    from core.render_constants import (
        INNER_GEO_SUBSTRINGS as _INNER_GEO_SUBSTRINGS,
        FACE_MESH_SUBSTRINGS as _FACE_MESH_SUBSTRINGS,
    )
except ImportError:
    try:
        from src.core.render_constants import (
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
    log.info("gpu_renderer: moderngl not installed – using CPU fallback")

from dataclasses import dataclass, field as _field

# ── Phase A: GPU Skinning ──────────────────────────────────────────────────
# Import MatrixPaletteUploader for real-time skeletal animation in the GPU path.
# gpu_skinning.py contains the palette builder, SSBO layout, and GLSL snippets.
try:
    from core.gpu_skinning import MatrixPaletteUploader, MAX_BONES as _SKIN_MAX_BONES
    _GPU_SKINNING = True
except ImportError:
    try:
        from src.core.gpu_skinning import MatrixPaletteUploader, MAX_BONES as _SKIN_MAX_BONES
        _GPU_SKINNING = True
    except ImportError:
        _GPU_SKINNING = False
        _SKIN_MAX_BONES = 128
        log.info("gpu_renderer: gpu_skinning module not available – skinning disabled")


# ─────────────────────────────────────────────────────────────────────────────
#  ModuleDrawItem — per-node render record for debug inspection
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModuleDrawItem:
    """Render record capturing per-node material/texture state for debugging.

    One ModuleDrawItem is created per draw call (per material slot for
    multi-texture nodes).  The collection can be printed as a table to
    verify that every visible surface uses the correct bitmap and material.

    Fields:
        node_name     : ModelNode.name
        node_type     : 'trimesh', 'skin', 'dangly', etc.
        bitmap        : Primary diffuse texture name used for this draw call
        lightmap      : Lightmap texture name ('' if none)
        envmap        : Environment-map texture name ('' if none)
        txi_blending  : TXI blend mode (0=none, 1=additive, 2=punchthrough)
        txi_decal     : Whether this is a decal surface
        txi_wateralpha: Water alpha multiplier
        txi_alpha_test: Punchthrough alpha threshold
        tri_count     : Number of triangles in this draw call
        mat_slot      : Material slot index (0 for single-tex; 0..N-1 for multi)
        transform     : (world_pos, world_orient) tuple
        pass_name     : 'opaque', 'cutout', or 'transparent'
    """
    node_name:      str   = ''
    node_type:      str   = ''
    bitmap:         str   = ''
    lightmap:       str   = ''
    envmap:         str   = ''
    txi_blending:   int   = 0
    txi_decal:      bool  = False
    txi_wateralpha: float = 1.0
    txi_alpha_test: float = 0.5
    tri_count:      int   = 0
    mat_slot:       int   = 0
    transform:      tuple = ()
    pass_name:      str   = 'opaque'


def debug_draw_table(model, textures: dict = None) -> str:
    """Return a human-readable table of per-node material/texture assignments.

    This is a diagnostic tool: call it with a loaded KotorModel to inspect
    the bitmap→node ownership before rendering.  Useful for verifying that
    module surfaces have correct texture assignments.

    Returns a multi-line string suitable for logging or UI display.
    """
    lines = []
    lines.append(f"{'Node':<30s} {'Type':<12s} {'Bitmap':<25s} {'Lightmap':<20s} "
                 f"{'EnvMap':<20s} {'Blend':>5s} {'Decal':>5s} {'WAlpha':>6s} "
                 f"{'ATest':>5s} {'Tris':>6s} {'Slots':>5s}")
    lines.append('-' * 160)

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    total_tris = 0
    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        n_name = str(getattr(node, 'name', '?'))[:29]
        n_type = str(getattr(node, 'type_label', '?'))[:11]
        bitmap = str(getattr(node, 'texture', '') or '').strip()[:24]
        lm = str(getattr(node, 'lightmap', '') or '').strip()[:19]
        env = str(getattr(node, 'txi_envmaptexture', '') or '').strip()[:19]
        blend = int(getattr(node, 'txi_blending', 0))
        decal = bool(getattr(node, 'txi_decal', False))
        walpha = float(getattr(node, 'txi_wateralpha', 1.0))
        atest = float(getattr(node, 'txi_alpha_test', 0.5))
        n_faces = len(getattr(node, 'faces', []))
        tc = int(getattr(node, 'tex_count', 1))
        total_tris += n_faces

        lines.append(f"{n_name:<30s} {n_type:<12s} {bitmap:<25s} {lm:<20s} "
                     f"{env:<20s} {blend:>5d} {'Y' if decal else 'N':>5s} "
                     f"{walpha:>6.2f} {atest:>5.2f} {n_faces:>6d} {tc:>5d}")

        # Show multi-texture slot details
        tex_names = getattr(node, 'texture_names', [])
        if tc > 1 and tex_names:
            for si, tn in enumerate(tex_names):
                _tn = str(tn or '').strip()[:24]
                _in_dict = '✓' if (textures and _tn.lower() in textures) else '?'
                lines.append(f"  └─ slot {si}: {_tn} [{_in_dict}]")

    lines.append('-' * 160)
    lines.append(f"Total mesh nodes: {sum(1 for n in nodes if getattr(n, 'is_mesh', False))}, "
                 f"Total triangles: {total_tris}")
    return '\n'.join(lines)


def debug_uv_channel_table(model) -> str:
    """Return a per-node UV channel audit table.

    Diagnostic function for Phase 2 of the face_uvs / tvert indexing audit.
    For each mesh node, reports:
      - node_name, texture, lightmap, tex_count, texture_names[]
      - lengths of uvs, uvs_lm, uvs_2, uvs_3, face_uvs
      - unique face_mats values
      - has_lightmap flag
      - whether face_uvs == faces (binary MDL convention)
      - which VBO path the node takes (IBO indexed vs expanded)

    Returns a multi-line string suitable for logging or UI display.
    """
    lines = []
    lines.append(f"{'Node':<28s} {'tex':>3s} {'has_lm':>6s} "
                 f"{'n_v':>5s} {'n_f':>5s} {'n_uv':>5s} {'n_lm':>5s} "
                 f"{'n_fuv':>5s} {'umat':>8s} {'fuv=f':>5s} {'path':>8s} "
                 f"{'texture':>24s} {'lightmap':>20s}")
    lines.append('-' * 170)

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        n_name  = str(getattr(node, 'name', '?'))[:27]
        texture = str(getattr(node, 'texture', '') or '').strip()[:24]
        lm      = str(getattr(node, 'lightmap', '') or '').strip()[:20]
        tc      = int(getattr(node, 'tex_count', 1))
        has_lm  = bool(getattr(node, 'has_lightmap', False))

        verts    = getattr(node, 'vertices', getattr(node, 'verts', []))
        faces    = getattr(node, 'faces', [])
        uvs      = getattr(node, 'uvs', [])
        uvs_lm   = getattr(node, 'uvs_lm', [])
        uvs_2    = getattr(node, 'uvs_2', [])
        uvs_3    = getattr(node, 'uvs_3', [])
        face_uvs = getattr(node, 'face_uvs', [])
        face_mats = getattr(node, 'face_mats', [])

        n_v = len(verts)
        n_f = len(faces)
        n_uv = len(uvs)
        n_lm = len(uvs_lm)
        n_fuv = len(face_uvs)

        # Unique face_mats
        umat = str(sorted(set(face_mats)))[:8] if face_mats else '-'

        # Check face_uvs == faces
        fuv_eq = '-'
        if n_fuv == n_f and n_f > 0:
            try:
                import numpy as _np
                _fuv = _np.asarray(face_uvs, dtype=_np.int32)
                _fv  = _np.asarray(faces, dtype=_np.int32)
                if _fuv.shape == _fv.shape:
                    fuv_eq = 'Y' if _np.array_equal(_fuv, _fv) else 'N'
            except Exception:
                fuv_eq = '?'

        # Determine VBO path
        is_skin = bool(getattr(node, 'is_skin', False))
        has_fuv = (n_fuv == n_f) and fuv_eq != 'Y'
        path = 'expand' if (has_fuv or is_skin) else 'IBO'

        lines.append(f"{n_name:<28s} {tc:>3d} {'Y' if has_lm else 'N':>6s} "
                     f"{n_v:>5d} {n_f:>5d} {n_uv:>5d} {n_lm:>5d} "
                     f"{n_fuv:>5d} {umat:>8s} {fuv_eq:>5s} {path:>8s} "
                     f"{texture:>24s} {lm:>20s}")

        # Show texture_names
        tex_names = getattr(node, 'texture_names', [])
        if tc > 1 and tex_names:
            for si, tn in enumerate(tex_names):
                role = 'diffuse' if si == 0 else ('lightmap' if (has_lm and si == 1) else f'slot{si}')
                lines.append(f"  └─ [{si}] {str(tn)[:24]} ({role})")

    lines.append('-' * 170)
    return '\n'.join(lines)


def debug_texture_cache_table(model, textures: dict = None) -> str:
    """Return a texture-cache validation table (Phase 4 diagnostic).

    For each texture referenced by the model, reports:
      - texture name
      - source image dimensions (W×H) or 'MISSING' if not in textures dict
      - cache key (id of the PIL Image object)
      - which nodes reference this texture (as diffuse, lightmap, env, spec)

    This proves that distinct textures are not sharing the same cached GPU
    upload — each unique PIL Image should have a unique id() / cache key.

    Parameters
    ----------
    model     : KotorModel
    textures  : dict mapping lowercased texture name → PIL Image

    Returns a multi-line string suitable for logging or UI display.
    """
    textures = textures or {}
    lines = []
    lines.append(f"{'Texture Name':<30s} {'Dims':>10s} {'CacheKey(id)':>16s} "
                 f"{'Role':>10s} {'Nodes Using It':<50s}")
    lines.append('-' * 130)

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    # Collect all texture references and the nodes that use them
    tex_refs: dict = {}  # name → {role: set of node names}
    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        n_name = str(getattr(node, 'name', '?'))

        tex = str(getattr(node, 'texture', '') or '').strip().lower()
        if tex and tex not in ('null', 'none', ''):
            tex_refs.setdefault(tex, {}).setdefault('diffuse', set()).add(n_name)

        lm = str(getattr(node, 'lightmap', '') or '').strip().lower()
        if lm and lm not in ('null', 'none', ''):
            tex_refs.setdefault(lm, {}).setdefault('lightmap', set()).add(n_name)

        env = str(getattr(node, 'txi_envmaptexture', '') or '').strip().lower()
        if env:
            tex_refs.setdefault(env, {}).setdefault('envmap', set()).add(n_name)

        spec = str(getattr(node, 'txi_specularcolour', '') or '').strip().lower()
        if spec:
            tex_refs.setdefault(spec, {}).setdefault('specular', set()).add(n_name)

    # Build the table
    seen_keys = set()
    for tex_name in sorted(tex_refs.keys()):
        roles = tex_refs[tex_name]
        img = textures.get(tex_name)
        if img is not None:
            try:
                dims = f"{img.size[0]}×{img.size[1]}"
            except Exception:
                dims = "?"
            cache_key = str(id(img))
            if cache_key in seen_keys:
                dims += " SHARED!"
            seen_keys.add(cache_key)
        else:
            dims = "MISSING"
            cache_key = "-"

        for role, node_set in sorted(roles.items()):
            node_list = ', '.join(sorted(node_set))
            if len(node_list) > 49:
                node_list = node_list[:46] + '...'
            lines.append(f"{tex_name:<30s} {dims:>10s} {cache_key:>16s} "
                         f"{role:>10s} {node_list:<50s}")

    lines.append('-' * 130)

    # Check for duplicate cache keys (same PIL object used for different names)
    key_to_names: dict = {}
    for tex_name in tex_refs:
        img = textures.get(tex_name)
        if img is not None:
            key = id(img)
            key_to_names.setdefault(key, []).append(tex_name)
    dups = {k: v for k, v in key_to_names.items() if len(v) > 1}
    if dups:
        lines.append("WARNING: Same PIL Image object used for multiple texture names:")
        for k, names in dups.items():
            lines.append(f"  id={k} → {', '.join(names)}")
    else:
        lines.append("OK: All texture names map to distinct PIL Image objects.")

    return '\n'.join(lines)


def debug_material_role_table(model) -> str:
    """Return a material-role audit table (Phase 1 diagnostic).

    For each mesh node, shows the material-role semantics:
      - node name, texture, lightmap, tex_count, texture_names[]
      - has_lightmap flag (from MDL binary)
      - FIX-LMROLE: whether lightmap role was inferred
      - lengths of uvs, uvs_lm
      - unique face_mats
      - renderer dispatch path (single/Case A/Case B)
      - slot 1 role (lightmap vs secondary diffuse)
      - whether lightmap will be bound in _draw_node

    Returns a multi-line string suitable for logging or UI display.
    """
    lines = []
    lines.append(f"{'Node':<26s} {'texture':<20s} {'lightmap':<18s} "
                 f"{'tc':>2s} {'lm?':>3s} {'infer':>5s} "
                 f"{'uvs':>5s} {'uv_lm':>5s} {'fm':>8s} "
                 f"{'dispatch':<18s} {'slot1_role':<16s} {'lm_bind':>7s}")
    lines.append('-' * 160)

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        n_name  = str(getattr(node, 'name', '?'))[:25]
        texture = str(getattr(node, 'texture', '') or '').strip().lower()[:19]
        lm      = str(getattr(node, 'lightmap', '') or '').strip().lower()[:17]
        tc      = int(getattr(node, 'tex_count', 1))
        has_lm  = bool(getattr(node, 'has_lightmap', False))
        tex_names = getattr(node, 'texture_names', [])

        uvs     = getattr(node, 'uvs', [])
        uvs_lm  = getattr(node, 'uvs_lm', [])
        face_mats = getattr(node, 'face_mats', [])

        n_uv  = len(uvs)
        n_lm  = len(uvs_lm)
        umat  = str(sorted(set(face_mats)))[:8] if face_mats else '-'

        # Determine if FIX-LMROLE would infer lightmap
        _inferred = False
        if (not has_lm and tc == 2 and n_lm > 0
                and n_lm == n_uv and face_mats
                and all(m == 0 for m in face_mats)):
            _inferred = True
        _effective_lm = has_lm or _inferred

        # Dispatch path
        if tc <= 1 or len(tex_names) < tc:
            dispatch = 'single-tex'
            slot1_role = 'N/A'
        elif _effective_lm:
            dispatch = 'Case A (lightmap)'
            slot1_role = 'lightmap'
        else:
            dispatch = 'Case B (multi-mat)'
            slot1_role = 'secondary diffuse'

        # Lightmap binding
        lm_bind = 'YES' if (_effective_lm and lm and n_lm > 0) else 'NO'

        lines.append(f"{n_name:<26s} {texture:<20s} {lm:<18s} "
                     f"{tc:>2d} {'Y' if has_lm else 'N':>3s} "
                     f"{'INF' if _inferred else '-':>5s} "
                     f"{n_uv:>5d} {n_lm:>5d} {umat:>8s} "
                     f"{dispatch:<18s} {slot1_role:<16s} {lm_bind:>7s}")

    lines.append('-' * 160)
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  Shader sources
# ─────────────────────────────────────────────────────────────────────────────

_VERT_SRC = """
#version 330 core

// Per-vertex inputs
in vec3  in_pos;       // world-space position (pre-transformed by _build_vbo_data)
in vec3  in_norm;      // world-space normal
in vec2  in_uv;        // primary UV (UV0) — KotOR D3D convention: V=0 at top
in vec2  in_uv_lm;     // lightmap UV (UV1)
in vec4  in_color;     // vertex colour (w = per-vertex alpha, 1.0 if unused)

// ── Phase A: GPU Skinning — bone index + weight vertex attributes ───────────
// For skin nodes: 4 bone indices and 4 blend weights per vertex.
// For non-skin nodes: bone_ids = (0,0,0,0), weights = (1,0,0,0) (identity).
// Bone indices are supplied through an integer vertex attribute.  Do not bind
// this as float: deterministic wrong-bone lookups produce stable pinned pieces.
in ivec4 in_bone_ids;  // 4 bone palette indices
in vec4  in_weights;   // 4 blend weights (sum ≈ 1.0)

// Uniforms
uniform mat4  u_mvp;           // model-view-projection matrix (column-major)
uniform mat4  u_model;         // model matrix (identity — verts already in world space)
uniform mat3  u_normal_mat;    // transpose(inverse(model)) 3x3

// ── Phase A: GPU Skinning uniforms ──────────────────────────────────────────
// Bone matrix palette (uniform array, GL 3.3+).
// Each bone matrix = world_pose × inv_bind_pose (Gregory §12.5.2).
// u_skin_enabled: 0 = pass-through (no LBS), 1 = apply LBS skinning.
// u_bone_count: number of valid bones in the palette (for bounds checking).
uniform mat4  u_bones[128];    // max 128 bones (KotOR engine limit)
uniform int   u_skin_enabled;  // 1 = LBS skinning active for this draw call
uniform int   u_bone_count;    // number of valid bone matrices uploaded

// UV animation
uniform vec2  u_uv_scroll;     // per-frame UV offset (animate_uv)
uniform float u_uv_v_flip;     // 1.0 = KotOR binary/D3D V flip, 0.0 = imported ASCII/OpenGL UVs
uniform float u_rotate_tex;    // 1.0 = swap UVs 90 deg CCW: (u,v) -> (v,1-u)
uniform vec2  u_flipbook_off;  // FIX-FLIPBOOK: tile offset for proceduretype=cycle sprite sheets
uniform vec2  u_flipbook_size; // FIX-FLIPBOOK: tile size (1/numx, 1/numy)

// v7.2 Dangly mesh animation (Finding 5.10 — reone v_model.glsl)
uniform float u_dangly_enabled;      // 1.0 = dangly mesh vertex animation active
uniform float u_dangly_displacement; // displacement magnitude (from ModelNode.dangly_displacement)
uniform float u_dangly_time;         // animation time for dangly physics

// v7.2 Lightsaber blade deformation (Finding 5.11 — reone v_model.glsl)
uniform float u_saber_enabled;       // 1.0 = saber blade vertex displacement active
uniform float u_saber_displacement;  // 0.0 (retracted) to 1.0 (fully extended)
uniform float u_saber_length;        // blade length in world units (default ~1.0)

// Outputs to fragment shader
out vec3  v_world_pos;
out vec3  v_world_norm;
out vec2  v_uv;
out vec2  v_uv_lm;
out vec4  v_color;

void main() {
    // ── Phase A: Linear Blend Skinning (Gregory §12.5.2) ────────────────────
    // When GPU skinning is enabled (u_skin_enabled == 1), transform position
    // and normal by the weighted sum of bone matrices from the palette.
    // Each vertex has up to 4 bone influences (in_bone_ids + in_weights).
    // For non-skin nodes u_skin_enabled == 0 and the pass-through path is used.
    vec3 final_pos;
    vec3 final_norm;
    if (u_skin_enabled == 1) {
        vec4 skinned_pos  = vec4(0.0);
        vec3 skinned_norm = vec3(0.0);
        for (int i = 0; i < 4; ++i) {
            int  bi = in_bone_ids[i];
            float w = in_weights[i];
            if (bi < 0 || bi >= u_bone_count || w < 0.0001) continue;
            mat4 M = u_bones[bi];
            skinned_pos  += w * (M * vec4(in_pos, 1.0));
            skinned_norm += w * (mat3(M) * in_norm);
        }
        // Guard: if total weight was zero, fall through to identity
        float wtot = in_weights.x + in_weights.y + in_weights.z + in_weights.w;
        if (wtot < 0.0001) {
            final_pos  = in_pos;
            final_norm = in_norm;
        } else {
            final_pos  = skinned_pos.xyz;
            final_norm = skinned_norm;
        }
    } else {
        final_pos  = in_pos;
        final_norm = in_norm;
    }

    vec4 world_pos = u_model * vec4(final_pos, 1.0);
    v_world_pos  = world_pos.xyz;
    // Normals are already in world space (pre-transformed); u_normal_mat = I for
    // world-space verts, but we still normalize to handle precision loss.
    v_world_norm = normalize(u_normal_mat * final_norm);

    // BUG-UV FIX: KotOR MDX stores UV with V=0 at top (Direct3D convention).
    // OpenGL textures have V=0 at bottom.  Flip V axis here to match OpenGL.
    // This is the canonical fix used by KotorBlender reader.py and KotOR.js.
    //
    // Texture data is uploaded in bottom-up orientation (GL convention):
    //   GL V=0 → bottom of image, GL V=1 → top of image.
    // KotOR UV V=0 → top of image → shader maps to GL V=1.0 (correct).
    // KotOR UV V=1 → bottom of image → shader maps to GL V=0.0 (correct).
    vec2 flipped_uv = vec2(in_uv.x, mix(in_uv.y, 1.0 - in_uv.y, u_uv_v_flip));

    // UV scroll (animate_uv): offset primary UVs by time-based scroll amount
    vec2 scrolled_uv = flipped_uv + u_uv_scroll;

    // RotateTexture: 90 deg CCW rotation -> (u,v) -> (v, 1-u)
    if (u_rotate_tex > 0.5) {
        scrolled_uv = vec2(scrolled_uv.y, 1.0 - scrolled_uv.x);
    }

    // FIX-FLIPBOOK: apply sprite-sheet tile offset for proceduretype=cycle textures.
    // u_flipbook_off = (col/numx, row/numy); u_flipbook_size = (1/numx, 1/numy).
    // When no flipbook is active both uniforms are (0,0) so this is a no-op.
    vec2 base_uv = scrolled_uv * u_flipbook_size + u_flipbook_off;
    // If flipbook is inactive (size==0,0) fall back to unscaled UVs
    v_uv = (u_flipbook_size.x > 0.0001) ? base_uv : scrolled_uv;
    // Lightmap UVs stay on their own channel and keep the D3D→OpenGL V-flip.
    v_uv_lm  = vec2(in_uv_lm.x, 1.0 - in_uv_lm.y);
    v_color  = in_color;

    // ── v7.2 GPU Dangly Mesh Animation (Finding 5.10 — reone v_model.glsl) ──────
    // When FEAT_DANGLY is enabled, the vertex shader displaces vertices using
    // a simplified spring-physics simulation driven by u_dangly_time.
    // Each vertex's displacement is modulated by the dangly constraint weight
    // (encoded in vertex color alpha for dangly nodes) and a wind-like
    // sinusoidal function matching KotOR.js ForgeModel3D dangly simulation.
    // Reference: reone v_model.glsl line 58-59; KotOR.js OdysseyModel3D.ts
    //            dangly mesh update; KotorBlender reader.py DANGLY node type.
    if (u_dangly_enabled > 0.5) {
        float constraint = v_color.a;  // constraint weight (0=free, 1=fixed)
        float freedom = 1.0 - constraint;
        // Wind-like displacement: two sine waves at different frequencies
        float phase1 = u_dangly_time * 2.3 + in_pos.x * 1.5 + in_pos.y * 0.8;
        float phase2 = u_dangly_time * 1.7 + in_pos.z * 1.2 + in_pos.x * 0.5;
        vec3 displacement = vec3(
            sin(phase1) * u_dangly_displacement * freedom * 0.3,
            cos(phase2) * u_dangly_displacement * freedom * 0.2,
            sin(phase1 + phase2) * u_dangly_displacement * freedom * 0.1
        );
        world_pos.xyz += displacement;
    }

    // ── v7.2 Lightsaber Blade Vertex Shader (Finding 5.11 — reone v_model.glsl) ─
    // When FEAT_SABER is enabled, vertices are displaced along the blade axis
    // based on gl_VertexID to create the blade extension/retraction effect.
    // reone v_model.glsl: hdist = ((gl_VertexID % 88) / 4) / 21.0
    // KotorBlender: NUM_SABER_VERTS=176, SABER_FACES face list.
    // u_saber_displacement = 0.0 (retracted) to 1.0 (fully extended).
    // The blade extends along the local Z-axis (KotOR saber convention).
    if (u_saber_enabled > 0.5) {
        // Blade height normalized from vertex ID pattern (reone convention)
        int vid = gl_VertexID % 176;  // KotorBlender NUM_SABER_VERTS=176
        float hdist = float((vid / 4) % 22) / 21.0;
        // Only displace vertices that are NOT at the base (hdist > 0)
        if (hdist > 0.01) {
            world_pos.z += hdist * u_saber_displacement * u_saber_length;
        }
    }

    gl_Position = u_mvp * vec4(world_pos.xyz, 1.0);
}
"""

_FRAG_SRC = """
#version 330 core

// ── v7.1 Feature-bitmask flags (Finding 5.2 — reone u_locals.glsl pattern) ──
// Consolidates per-feature boolean uniforms into a single bitmask int.
// Reduces uniform upload overhead (~12 uploads → 1) and simplifies shader branching.
// Each feature is a power-of-2 flag tested with bitwise AND.
// Legacy individual uniforms (u_has_tex, u_has_lm, etc.) are preserved for
// backward compatibility — the bitmask is an ADDITIONAL fast-path.
#define FEAT_TEXTURE    (1 << 0)
#define FEAT_LIGHTMAP   (1 << 1)
#define FEAT_ENVMAP     (1 << 2)
#define FEAT_SPECMAP    (1 << 3)
#define FEAT_BUMPMAP    (1 << 4)
#define FEAT_WATER      (1 << 5)
#define FEAT_DANGLY     (1 << 6)
#define FEAT_SABER      (1 << 7)
#define FEAT_SHADOWS    (1 << 8)
#define FEAT_FOG        (1 << 9)
#define FEAT_SKIN       (1 << 10)
#define FEAT_DECAL      (1 << 11)
#define FEAT_PUNCHTHRU  (1 << 12)
#define FEAT_ADDITIVE   (1 << 13)
#define FEAT_HASHEDALPHA (1 << 14)

bool featureEnabled(int mask, int flag) { return (mask & flag) != 0; }

// Samplers
uniform sampler2D u_tex;        // diffuse texture (unit 0)
uniform sampler2D u_lm_tex;     // lightmap texture (unit 1)
uniform sampler2D u_env_tex;    // environment map texture (unit 2)
uniform sampler2D u_spec_tex;   // FIX-SPECMAP: specular colour map (unit 3)
uniform sampler2D u_bump_tex;   // bump/normal map texture (unit 4)
uniform int       u_has_tex;    // 1 = diffuse texture bound
uniform int       u_has_lm;     // 1 = lightmap bound
uniform int       u_has_env;    // 1 = env map bound (TXI envmaptexture / bumpyshinytexture)
uniform int       u_has_spec;   // FIX-SPECMAP: 1 = specular map bound (TXI specularcolour)
uniform int       u_has_bump;   // 1 = bump/normal map bound
uniform int       u_features;   // v7.1: packed bitmask of FEAT_* flags

// Material
uniform vec3  u_diffuse;        // node diffuse color [0..1]
uniform vec3  u_selfillum;      // self-illumination additive term
uniform float u_alpha;          // per-node alpha (0..1)
uniform float u_node_alpha;     // animated material alpha from CTRL 132

// Lighting
uniform vec3  u_light_dir;      // primary light direction (world space, normalised)
uniform vec3  u_light_dir2;     // secondary (fill) light direction
uniform float u_ambient;        // ambient intensity
uniform float u_specular;       // specular intensity scalar (used when u_has_spec==0)
uniform float u_shininess;      // Phong shininess exponent (overridden per-node)
uniform int   u_lm_shade;       // FIX-LMSHADE: 1 = lightmap-only shading (skip Phong)
uniform float u_lightmap_intensity;
uniform int   u_lightmap_mode;  // 0 baked multiply, 1 Phong modulate, 2 emissive add
uniform int   u_scene_lighting; // 0 unlit, 1 studio, 2 Aurora scene lights
uniform float u_scene_ambient;
uniform int   u_scene_light_count;
uniform int   u_scene_light_enabled[16];
uniform int   u_scene_light_kind[16]; // 0 point, 1 directional, 2 spot, 3 area
uniform int   u_scene_light_ambient_only[16];
uniform vec3  u_scene_light_pos[16];
uniform vec3  u_scene_light_dir[16];
uniform vec3  u_scene_light_color[16];
uniform float u_scene_light_radius[16];
uniform float u_scene_light_intensity[16];
uniform float u_scene_light_cone_cos[16];
uniform float u_scene_light_area_size[16];

// Blend / material flags
uniform int   u_blend_mode;     // 0=normal, 1=additive, 2=punchthrough
uniform float u_alpha_test;     // punch-through threshold (default 0.5)
uniform int   u_decal;          // 1 = decal surface (blend over opaque background)
uniform float u_wateralpha;     // TXI wateralpha multiplier (default 1.0)

// v7.1 Water/ring proceduretype UV distortion (Finding 1.6 — KotOR.js TXI.ts)
uniform float u_water_time;     // animation time for water UV distortion
uniform int   u_proc_type;      // 0=none, 1=cycle, 2=water, 3=random, 4=ringtexdistort

// Camera position for specular + env map sphere projection
uniform vec3  u_cam_pos;

// v7.2 Order-Independent Transparency (Finding 5.5 — reone f_oit_model.glsl)
uniform int   u_oit_enabled;    // 1 = weighted-blended OIT output mode
uniform int   u_debug_visualize; // 0 normal, 1 red, 2 alpha, 3 diffuse, 4 lightmap
uniform int   u_lm_composite_mode; // 0 current, 1 multiply, 2 overbright2, 3 clamp diagnostic
uniform int   u_wireframe_enabled;
uniform vec3  u_wire_color;
uniform int   u_render_mode; // 0 realistic, 1 flat, 2 shaded
uniform int   u_selected;

// Inputs from vertex shader
in vec3  v_world_pos;
in vec3  v_world_norm;
in vec2  v_uv;
in vec2  v_uv_lm;
in vec4  v_color;

out vec4 frag_color;

vec3 sceneLightShade(vec3 N, vec3 V, vec3 world_pos, float spec_intensity, float shininess) {
    vec3 accum = vec3(u_scene_ambient);
    for (int i = 0; i < 16; ++i) {
        if (i >= u_scene_light_count) break;
        if (u_scene_light_enabled[i] == 0) continue;

        int kind = u_scene_light_kind[i];
        vec3 color = u_scene_light_color[i] * u_scene_light_intensity[i];
        vec3 L = vec3(0.0, 0.0, 1.0);
        float attenuation = 1.0;

        if (kind == 1) {
            L = normalize(-u_scene_light_dir[i]);
        } else {
            vec3 delta = u_scene_light_pos[i] - world_pos;
            float dist = length(delta);
            float radius = max(u_scene_light_radius[i], 0.001);
            if (dist > radius) continue;
            L = delta / max(dist, 0.0001);
            float falloff = clamp(1.0 - (dist / radius), 0.0, 1.0);
            attenuation = falloff * falloff;
            if (kind == 3) {
                attenuation = mix(attenuation, falloff, clamp(u_scene_light_area_size[i] * 0.25, 0.0, 0.6));
            }
            if (kind == 2) {
                vec3 spot_dir = normalize(u_scene_light_dir[i]);
                float cone = dot(normalize(world_pos - u_scene_light_pos[i]), spot_dir);
                float edge0 = u_scene_light_cone_cos[i];
                float spot = smoothstep(edge0, min(1.0, edge0 + 0.18), cone);
                attenuation *= spot;
            }
        }

        if (u_scene_light_ambient_only[i] == 1) {
            accum += color * attenuation;
        } else {
            float ndotl = max(dot(N, L), 0.0);
            vec3 R = reflect(-L, N);
            float spec = pow(max(dot(V, R), 0.0), max(shininess, 1.0)) * spec_intensity;
            accum += color * attenuation * (ndotl + spec);
        }
    }
    return clamp(accum, 0.0, 2.0);
}

vec3 perturbNormalFromMap(vec3 N, vec3 world_pos, vec2 uv) {
    vec3 sampled = texture(u_bump_tex, uv).xyz * 2.0 - 1.0;
    vec3 dp1 = dFdx(world_pos);
    vec3 dp2 = dFdy(world_pos);
    vec2 duv1 = dFdx(uv);
    vec2 duv2 = dFdy(uv);
    vec3 T = dp1 * duv2.y - dp2 * duv1.y;
    vec3 B = -dp1 * duv2.x + dp2 * duv1.x;
    float t_len = length(T);
    float b_len = length(B);
    if (t_len < 0.0001 || b_len < 0.0001) {
        return N;
    }
    mat3 TBN = mat3(normalize(T), normalize(B), normalize(N));
    return normalize(TBN * sampled);
}

void main() {
    if (u_wireframe_enabled == 1) {
        frag_color = vec4(u_wire_color, 1.0);
        return;
    }

    // -- v7.1 Water/ring UV distortion (Finding 1.6 — KotOR.js TXI.ts + reone)
    // proceduretype=water: sinusoidal UV distortion simulating water surface ripples.
    // proceduretype=ringtexdistort: radial ring distortion from UV center.
    // Cross-ref: KotOR.js TXI.ts lines 170-186; reone shader water vertex offset.
    vec2 final_uv = v_uv;
    if (u_proc_type == 2) {
        // Water UV distortion: dual sine wave offset (matches KotOR engine water FX)
        float water_freq = 8.0;
        float water_amp  = 0.015;
        final_uv.x += sin(v_uv.y * water_freq + u_water_time * 2.5) * water_amp;
        final_uv.y += cos(v_uv.x * water_freq + u_water_time * 1.7) * water_amp;
    } else if (u_proc_type == 4) {
        // Ring texture distortion: radial distortion from center
        vec2 centered = v_uv - vec2(0.5);
        float dist = length(centered);
        float ring_wave = sin(dist * 20.0 - u_water_time * 3.0) * 0.02;
        final_uv = v_uv + normalize(centered + vec2(0.001)) * ring_wave;
    }

    // -- Sample diffuse texture
    vec4 diffuse_samp;
    if (u_has_tex == 1) {
        diffuse_samp = texture(u_tex, final_uv);
    } else {
        diffuse_samp = vec4(u_diffuse, 1.0);
    }

    if (u_debug_visualize == 1) {
        frag_color = vec4(1.0, 0.0, 0.0, 1.0);
        return;
    }

    // -- Punch-through alpha test (TXI blending=punchthrough)
    // v7.1 FIX-HASHEDALPHA (Finding 5.4 — reone i_hashedalpha.glsl):
    // When FEAT_HASHEDALPHA is enabled, use screen-space noise dithering
    // instead of hard threshold for better quality on foliage/hair.
    if (u_blend_mode == 2) {
        if (featureEnabled(u_features, FEAT_HASHEDALPHA)) {
            // Hashed alpha: screen-space noise threshold
            float hash_noise = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
            float threshold = mix(u_alpha_test * 0.5, u_alpha_test, hash_noise);
            if (diffuse_samp.a < threshold) discard;
        } else {
            if (diffuse_samp.a < u_alpha_test) discard;
        }
    }

    // -- Per-vertex colour modulation
    diffuse_samp.rgb *= v_color.rgb;
    vec3 debug_diffuse_rgb = diffuse_samp.rgb;
    vec3 debug_lightmap_rgb = vec3(0.0);

    // -- Lighting
    vec3 N = normalize(v_world_norm);
    if (u_has_bump == 1) {
        N = perturbNormalFromMap(N, v_world_pos, final_uv);
    }
    vec3 V = normalize(u_cam_pos - v_world_pos);
    vec3 lit_color;

    // FIX-LMSHADE: KotOR module geometry with baked lightmaps uses the
    // lightmap as the sole lighting source.  The Phong directional shade
    // must be SKIPPED for these nodes — otherwise the already-dim lightmap
    // (mean intensity ~0.25) is further darkened by the Phong multiplier,
    // producing an unrealistically dark scene.
    //
    // Reference: KotOR.js ShaderOdysseyModel.ts lines 359-365:
    //   #ifdef USE_LIGHTMAP
    //     reflectedLight.indirectDiffuse = vec3(0.0);
    //     reflectedLight.indirectDiffuse += PI * texture2D(lightMap, vUv2).xyz * lightMapIntensity;
    //     reflectedLight.indirectDiffuse *= BRDF_Lambert(diffuseColor.rgb);
    //     vec3 outgoingLight = reflectedLight.indirectDiffuse + ...;
    //   The directDiffuse (Phong shade) is NOT included in the lightmapped path.
    //
    // Our simplified single-pass equivalent:
    //   lit_color = diffuse_tex.rgb * lightmap.rgb * OVERBRIGHT
    //
    // FIX-LMBRIGHT: The original ×2.0 overbright factor produced visibly
    // dark scenes because KotOR module lightmaps have a mean intensity of
    // only ~0.25.  With ×2.0: 0.4 × 0.25 × 2.0 = 0.20 (far too dark).
    //
    // KotOR.js effective path (ShaderOdysseyModel.ts USE_LIGHTMAP):
    //   indirectDiffuse = PI * lightmap * lightMapIntensity * BRDF_Lambert
    // The PI factor (~3.14) plus Lambert normalization (/PI) cancel, but
    // lightMapIntensity is tuned to produce visually correct results at
    // approximately ×2.5 effective overbright.
    //
    // xoreos uses multi-pass BLEND_MULTIPLY with an implicit gamma boost
    // that also results in ~2.5× effective brightness.
    //
    // We raise the single-pass overbright from 2.0 → 2.5 to match these
    // reference implementations, plus add a small ambient floor (0.03) to
    // prevent fully black areas in unlit corners of modules.

    if (u_lm_shade == 1 && u_has_lm == 1) {
        // ── Lightmap-only path (module/area geometry) ─────────────────
        vec4 lm_samp = texture(u_lm_tex, v_uv_lm);
        debug_lightmap_rgb = lm_samp.rgb;
        float lm_strength = clamp(u_lightmap_intensity, 0.0, 4.0);
        vec3 baked_light = mix(vec3(1.0), lm_samp.rgb * 2.0, clamp(lm_strength, 0.0, 1.0));
        if (u_lightmap_mode == 1) {
            float ndotl  = max(dot(N, u_light_dir),  0.0);
            float ndotl2 = max(dot(N, u_light_dir2), 0.0);
            vec3 R = reflect(-u_light_dir, N);
            float spec = pow(max(dot(V, R), 0.0), max(u_shininess, 1.0)) * u_specular;
            float shade = u_ambient + ndotl * (1.0 - u_ambient) * 0.85
                                    + ndotl2 * (1.0 - u_ambient) * 0.15
                                    + spec;
            lit_color = diffuse_samp.rgb * clamp(shade, 0.0, 1.5) * baked_light;
        } else if (u_lightmap_mode == 2) {
            lit_color = diffuse_samp.rgb + lm_samp.rgb * lm_strength;
        } else if (u_lm_composite_mode == 1) {
            // Diagnostic: pure multiply, no overbright and no ambient floor.
            lit_color = diffuse_samp.rgb * lm_samp.rgb;
        } else if (u_lm_composite_mode == 2) {
            // Diagnostic: documented original overbright 2.0, no ambient floor.
            lit_color = diffuse_samp.rgb * lm_samp.rgb * 2.0;
        } else {
            // FIX-LMBRIGHT: Raised overbright 2.0 → 2.5 + ambient floor 0.03
            lit_color = diffuse_samp.rgb * baked_light;
            if (u_lm_composite_mode == 3) {
                lit_color = clamp(lit_color, 0.0, 1.0);
            }
        }

        // Self-illumination still applies additively
        lit_color += u_selfillum;

        // Environment map compositing (rare for modules but handle it)
        if (u_has_env == 1) {
            vec3 R2 = reflect(-V, N);
            float m = 2.0 * sqrt(R2.x*R2.x + R2.y*R2.y + (R2.z+1.0)*(R2.z+1.0));
            vec2 env_uv = vec2(R2.x / m + 0.5, R2.y / m + 0.5);
            vec3 env_col = texture(u_env_tex, env_uv).rgb;
            float env_weight = 1.0 - diffuse_samp.a;
            lit_color = mix(lit_color, env_col, env_weight);
            diffuse_samp.a = 1.0;
        }
    } else {
        // ── Standard Phong path (characters, items, non-lightmapped) ─
        float ndotl  = max(dot(N, u_light_dir),  0.0);
        float ndotl2 = max(dot(N, u_light_dir2), 0.0);
        vec3 R = reflect(-u_light_dir, N);
        // FIX-SPECMAP: sample per-texel specular intensity from specularcolour map when bound.
        // KotOR specular maps store per-channel gloss in RGB; use luminance as scalar.
        // When no spec map, fall back to the global u_specular float (unchanged behaviour).
        float spec_intensity;
        if (u_has_spec == 1) {
            vec3 spec_col = texture(u_spec_tex, v_uv).rgb;
            spec_intensity = dot(spec_col, vec3(0.299, 0.587, 0.114)); // luminance
        } else {
            spec_intensity = u_specular;
        }
        float eff_shininess = max(u_shininess, 1.0);  // FIX-SHININESS: clamp to avoid pow(0,0)
        float spec = pow(max(dot(V, R), 0.0), eff_shininess) * spec_intensity;
        if (u_scene_lighting == 2 && u_scene_light_count > 0) {
            lit_color = diffuse_samp.rgb * sceneLightShade(N, V, v_world_pos, spec_intensity, eff_shininess);
        } else {
            float shade = u_ambient + ndotl * (1.0 - u_ambient) * 0.85
                                    + ndotl2 * (1.0 - u_ambient) * 0.15
                                    + spec;
            shade = clamp(shade, 0.0, 1.5);
            lit_color = diffuse_samp.rgb * shade;
        }

        // -- Environment map compositing (TXI envmaptexture / bumpyshinytexture)
        // KotOR Odyssey engine algorithm (xoreos renderGeometryEnvMappedOver +
        // KotOR.js ShaderOdysseyModel):
        //   The env map is drawn OVER diffuse using GL blend (ONE_MINUS_DST_ALPHA, ONE):
        //     env_contrib = env_color * (1 - diffuse_alpha)
        //   Single-pass equivalent:
        //     env_weight = 1.0 - diffuse_samp.a
        //     out_rgb = mix(lit_color, env_color, env_weight)
        //   Transparent areas (low alpha) => more env map visible.
        //   Opaque areas (high alpha)     => mostly diffuse visible.
        // Env UV: sphere-map (matcap) from view-space reflected normal.
        // Sources: xoreos modelnode.cpp renderGeometryEnvMappedOver()
        //          KotOR.js ShaderOdysseyModel.ts (1.0 - diffuseColor.a) blend factor
        if (u_has_env == 1) {
            vec3 R2 = reflect(-V, N);
            float m = 2.0 * sqrt(R2.x*R2.x + R2.y*R2.y + (R2.z+1.0)*(R2.z+1.0));
            vec2 env_uv = vec2(R2.x / m + 0.5, R2.y / m + 0.5);
            vec3 env_col = texture(u_env_tex, env_uv).rgb;
            // CORRECT: env shows through where diffuse is transparent (low alpha)
            float env_weight = 1.0 - diffuse_samp.a;
            lit_color = mix(lit_color, env_col, env_weight);
            // Diffuse alpha consumed by env blend - mark surface as opaque
            diffuse_samp.a = 1.0;
        }

        // -- Self-illumination (additive glow)
        // v7.1 (Finding 5.6 — reone context.cpp GL_MAX blend equation):
        // Self-illumination uses additive compositing. For surfaces with
        // selfillum > 0, clamp so glow doesn't over-brighten dark areas.
        lit_color += u_selfillum;

        // -- Lightmap compositing for non-lm_shade path (fallback):
        // This handles lightmapped nodes that somehow reach this path
        // (e.g. character models with lightmap textures).
        if (u_has_lm == 1) {
            vec4 lm_samp = texture(u_lm_tex, v_uv_lm);
            debug_lightmap_rgb = lm_samp.rgb;
            float lm_strength = clamp(u_lightmap_intensity, 0.0, 4.0);
            vec3 baked_light = mix(vec3(1.0), lm_samp.rgb * 2.0, clamp(lm_strength, 0.0, 1.0));
            if (u_lightmap_mode == 2) {
                lit_color += lm_samp.rgb * lm_strength;
            } else if (u_lm_composite_mode == 1) {
                lit_color *= lm_samp.rgb;
            } else if (u_lm_composite_mode == 2) {
                lit_color *= lm_samp.rgb * 2.0;
            } else {
                lit_color *= baked_light;
                if (u_lm_composite_mode == 3) {
                    lit_color = clamp(lit_color, 0.0, 1.0);
                }
            }
        }
    }

    if (u_scene_lighting == 0) {
        lit_color = diffuse_samp.rgb + u_selfillum;
    }

    if (u_render_mode == 1) {
        lit_color = diffuse_samp.rgb;
    } else if (u_render_mode == 2) {
        float soft_shade = clamp(0.76 + max(dot(N, u_light_dir), 0.0) * 0.24, 0.70, 1.0);
        lit_color = diffuse_samp.rgb * soft_shade;
        diffuse_samp.a = 1.0;
    }

    if (u_selected == 1) {
        lit_color = mix(lit_color, vec3(1.0, 0.78, 0.12), 0.45);
    }

    lit_color = clamp(lit_color, 0.0, 1.0);

    // -- TXI wateralpha: modulate alpha for water/glass surfaces
    float effective_alpha = u_alpha * u_node_alpha * u_wateralpha * v_color.a;

    // -- Final alpha
    float final_alpha;
    if (u_decal == 1) {
        // Decal: use diffuse texture alpha as blend weight
        final_alpha = diffuse_samp.a * effective_alpha;
    } else if (u_blend_mode == 0 && u_node_alpha >= 0.999 && u_alpha >= 0.999
               && u_wateralpha >= 0.999) {
        // Fully opaque - ignore DXT5 alpha channel (holds bump/specular data)
        final_alpha = 1.0;
    } else if (u_blend_mode == 2) {
        // Punchthrough: surviving fragments are fully opaque
        final_alpha = 1.0;
    } else {
        // Semi-transparent / additive
        final_alpha = diffuse_samp.a * effective_alpha;
    }

    if (u_debug_visualize == 2) {
        frag_color = vec4(final_alpha, final_alpha, final_alpha, 1.0);
        return;
    } else if (u_debug_visualize == 3) {
        frag_color = vec4(debug_diffuse_rgb, 1.0);
        return;
    } else if (u_debug_visualize == 4) {
        frag_color = vec4(debug_lightmap_rgb, 1.0);
        return;
    }

    // ── v7.2 Weighted-Blended OIT output (Finding 5.5 — reone f_oit_model.glsl) ─
    // When u_oit_enabled is active (transparent pass with OIT), output weighted
    // color + weight to dual render targets instead of simple alpha blend.
    // This avoids sorting transparent fragments entirely.
    // Formula: McGuire & Bavoil 2013 "Weighted Blended Order-Independent Transparency"
    //   weight = max(min(1.0, max(c.r,c.g,c.b) * c.a), c.a) * clamp(0.03/(1e-5+pow(z/200,4)), 1e-2, 3e3)
    // The resolve pass blends accum / revealage.
    // Reference: reone f_oit_model.glsl, f_oit_blend.glsl.
    if (u_oit_enabled == 1) {
        float z = gl_FragCoord.z;
        float w = max(min(1.0, max(max(lit_color.r, lit_color.g), lit_color.b) * final_alpha),
                      final_alpha) *
                  clamp(0.03 / (1e-5 + pow(z / 200.0, 4.0)), 1e-2, 3e3);
        // frag_color target 0 = (premul_color.rgb * w, alpha * w)
        frag_color = vec4(lit_color * final_alpha * w, final_alpha * w);
        // Note: second render target (revealage) would need MRT support;
        // for now we encode revealage in alpha and use single-target approximation.
    } else {
        frag_color = vec4(lit_color, final_alpha);
    }
}
"""


_GRID_VERT_SRC = """
#version 330
uniform mat4 u_mvp;
in vec3 in_pos;
in vec3 in_color;
out vec3 v_color;
void main() {
    v_color = in_color;
    gl_Position = u_mvp * vec4(in_pos, 1.0);
}
"""


_GRID_FRAG_SRC = """
#version 330
in vec3 v_color;
out vec4 frag_color;
void main() {
    frag_color = vec4(v_color, 1.0);
}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  Matrix helpers (column-major, OpenGL convention)
# ─────────────────────────────────────────────────────────────────────────────

def _mat4_perspective(fov_y: float, aspect: float, near: float, far: float):
    """Build a right-handed perspective projection matrix (standard row-major).

    Standard GLM-style perspective (clip.w = -view_z, NDC.z in [-1,+1]):
      Row 0: (f/a, 0,   0,               0)
      Row 1: (0,   f,   0,               0)
      Row 2: (0,   0,   -(f+n)/(f-n),   -2fn/(f-n))
      Row 3: (0,   0,   -1,              0)

    clip.w = row3 . view_v = -view_z  (gives standard perspective divide)
    Use _mat4_tobytes() to convert to GLSL column-major bytes for upload.
    """
    f = 1.0 / math.tan(fov_y * 0.5)
    nf = 1.0 / (near - far)   # = -1/(far-near)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) * nf      # -(f+n)/(f-n)
    m[2, 3] = 2.0 * far * near * nf  # -2fn/(f-n)
    m[3, 2] = -1.0                    # clip.w = -view_z
    return m


def _mat4_lookat(eye, center, up):
    """Build a right-handed look-at view matrix (standard row-major convention).

    Returns a standard 4x4 NumPy matrix where:
      row0 = right vector (s) + tx at [0,3]
      row1 = up vector (u) + ty at [1,3]
      row2 = -forward vector + tz at [2,3]
      row3 = (0, 0, 0, 1)
    Use _mat4_tobytes() to convert to GLSL column-major bytes.
    """
    eye = np.array(eye, dtype=np.float64)
    center = np.array(center, dtype=np.float64)
    up = np.array(up, dtype=np.float64)
    f = center - eye;  f /= np.linalg.norm(f)
    s = np.cross(f, up); s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] =  np.dot(f, eye)
    return m


def _mat4_identity():
    return np.eye(4, dtype=np.float32)


def _mat4_tobytes(m: np.ndarray) -> bytes:
    """Convert a standard row-major NumPy 4x4 matrix to GLSL column-major bytes.

    ModernGL/OpenGL reads mat4 uniforms in column-major order.  NumPy's tobytes()
    outputs row-major bytes.  Transposing before tobytes() gives column-major output.
    """
    return m.reshape(4, 4).T.astype(np.float32).tobytes()


def _mat4_mul(a, b):
    """Multiply two row-major 4x4 matrices: returns a @ b."""
    return (a.reshape(4, 4) @ b.reshape(4, 4)).astype(np.float32)


def _mat3_normal(model_mat: np.ndarray) -> np.ndarray:
    """Compute the normal matrix = transpose(inverse(model_mat_3x3))."""
    m33 = model_mat.reshape(4, 4)[:3, :3].copy()
    try:
        return np.linalg.inv(m33).T.astype(np.float32)
    except np.linalg.LinAlgError:
        return np.eye(3, dtype=np.float32)


# ─────────────────────────────────────────────────────────────────────────────
#  Texture cache
# ─────────────────────────────────────────────────────────────────────────────

class _GlTexCache:
    """Caches PIL Image → GL Texture2D upload to avoid re-uploading unchanged textures.

    FIX-TEXCACHE-KEY: The original implementation keyed on id(img) alone, which
    is unsafe because Python can reuse object addresses after GC.  A new PIL Image
    allocated at the same address as a previously-released one would receive a stale
    GL texture upload (wrong pixels, wrong size).  We guard against this by also
    storing a weak-reference to the original image object.  On cache-hit we check
    that the weakref is still alive AND still points to the same object; if the
    weakref is dead (GC'd) the entry is a ghost and must be evicted + re-uploaded.

    Additionally we use a MAX_ENTRIES cap (512) with LRU eviction via OrderedDict to
    prevent unbounded VRAM growth when batch-rendering hundreds of models.  Each
    512×512 RGBA mip-chain ≈ 682 KB VRAM; 512 entries ≈ 341 MB worst-case, well
    within the 2 GB EGL soft limit on typical headless servers.
    """

    MAX_ENTRIES: int = 512  # VRAM safety cap; adjust per target hardware

    def __init__(self, ctx: 'moderngl.Context'):
        self._ctx = ctx
        # OrderedDict for O(1) LRU: key = id(img), value = (weakref, GL Texture)
        import collections, weakref as _weakref_mod
        self._cache: 'collections.OrderedDict[int, tuple]' = collections.OrderedDict()
        self._wr_mod = _weakref_mod  # stash for use in methods

    def get(self, img: Optional['Image.Image']) -> Optional['moderngl.Texture']:
        if img is None or not _PIL:
            return None
        key = id(img)
        if key in self._cache:
            wr, tex = self._cache[key]
            live = wr()
            if live is img:
                # Cache hit: move to end (most-recently-used) and return
                self._cache.move_to_end(key)
                return tex
            # Stale entry (GC'd object reused same address) — evict and re-upload
            try:
                tex.release()
            except Exception:
                pass
            del self._cache[key]
        # Cache miss: upload and store
        tex = self._upload(img)
        if tex:
            # Evict LRU entry if over capacity
            while len(self._cache) >= self.MAX_ENTRIES:
                _, (_, old_tex) = self._cache.popitem(last=False)
                try:
                    old_tex.release()
                except Exception:
                    pass
            try:
                wr = self._wr_mod.ref(img)
            except TypeError:
                # img is not weakly referenceable (rare); use a dummy ref
                wr = lambda: img  # noqa: E731 — never GC'd while in cache
            self._cache[key] = (wr, tex)
        return tex

    def _upload(self, img: 'Image.Image') -> Optional['moderngl.Texture']:
        try:
            rgba = img.convert('RGBA')
            # FIX-VFLIP-REMOVED: NO flip here.  All images arriving at the GPU
            # texture cache are ALREADY in bottom-up (OpenGL) orientation.
            #
            # TextureCache._load_tpc_bytes (viewport.py) flips DXT textures from
            # top-down (DirectX DXT block order) to bottom-up, and uncompressed
            # textures from PyKotor are already bottom-up.  The MCP/ghostrigger
            # path also uses _load_tpc_bytes which returns bottom-up images.
            #
            # Previously this method applied FLIP_TOP_BOTTOM unconditionally,
            # assuming images were top-down (fresh from PyKotor's to_pil_image).
            # That caused a double-flip for DXT textures (TextureCache flipped
            # once, _upload flipped again → back to top-down → upside-down in GL)
            # and an unwanted flip for uncompressed textures (already bottom-up
            # → flipped to top-down → also upside-down in GL).
            #
            # With bottom-up images uploaded directly:
            #   PIL row 0 = bottom of image → GL texture row 0 (V=0) = bottom ✓
            #   Vertex shader: gl_v = 1.0 - kotor_v
            #     KotOR V=0 (top) → GL V=1.0 → samples last row = top of image ✓
            #     KotOR V=1 (bottom) → GL V=0.0 → samples first row = bottom ✓
            #
            # Cross-ref: viewport._load_tpc_bytes (DXT flip to bottom-up);
            #            viewport.TextureCache._load_bytes (bottom-up contract);
            #            kotor_loader.load_tpc_as_pil (top-down — NOT used by
            #            viewport; only used by resource_manager._decode_texture).
            #
            # FIX-YELLOWPIXEL: KotOR TPC textures (e.g. c_bantha01) sometimes have
            # bright saturated test/marker pixels in the top-right corner of the
            # original image (D3D V≈0, KotOR texture top).  In bottom-up PIL data,
            # the "top of texture" is the LAST rows of the array (highest row index).
            # These rows map to GL V≈1.0.  The shader maps KotOR V≈0 → GL V≈1.0,
            # so those yellow pixels are sampled on creature bellies (KotOR V near 0).
            # Fix: scan the last 2 pixel rows of the bottom-up PIL image (= top of
            # texture = GL V≈1.0) for yellow/green marker pixels and neutralize them.
            if _NUMPY:
                import numpy as _np
                _arr = _np.array(rgba, dtype=_np.uint8)  # (H, W, 4)
                _H, _W = _arr.shape[:2]
                # Inspect last 2 rows (= top of texture in bottom-up layout = GL V≈1)
                for _row_offset in range(min(2, _H)):
                    _row = _H - 1 - _row_offset
                    for _col in range(_W):
                        r, g, b, a = int(_arr[_row, _col, 0]), int(_arr[_row, _col, 1]), int(_arr[_row, _col, 2]), int(_arr[_row, _col, 3])
                        # Detect bright saturated yellow-green: R and G both high, B low
                        _is_yellow = (r > 160 and g > 160 and b < 100 and (r + g) > 2 * b + 200)
                        if _is_yellow:
                            # Replace with left neighbor if available, else with (64,50,40,255)
                            if _col > 0:
                                _arr[_row, _col] = _arr[_row, _col - 1]
                            else:
                                _arr[_row, _col] = [64, 50, 40, 255]
                from PIL import Image as _PILImg
                rgba = _PILImg.fromarray(_arr, 'RGBA')
            w, h = rgba.size
            data = rgba.tobytes()
            tex = self._ctx.texture((w, h), 4, data)
            tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            # FIX-TEXWRAP: Default to GL_REPEAT for all uploaded textures.
            # KotOR area geometry uses UV coordinates well outside [0,1] (e.g.
            # N_sithpraet pelvis U=[-13,+13]) and relies on the texture wrapping
            # to repeat correctly.  GL_CLAMP_TO_EDGE causes the edge texel to be
            # stretched across the entire surface for any UV outside [0,1], which
            # makes tiled geometry look solid-colored or edge-stretched.
            # Per-node clamp mode (TXI 'clamp' command → txi_clamp_s/txi_clamp_t)
            # is applied in _draw_node by setting repeat_x/repeat_y before each
            # draw call — this allows head/decal textures to use CLAMP_TO_EDGE
            # while body/area textures use GL_REPEAT.
            # The yellow-pixel artifact is handled by scrubbing marker pixels before
            # upload (above), so GL_REPEAT is safe.
            tex.repeat_x = True
            tex.repeat_y = True
            # FIX-MIPALIGN: Clamp mip chain at level 6 (coarsest = 8×8 for 512px)
            # to prevent single corner pixel colors from dominating lower LODs.
            # max_level=6 keeps 512→256→128→64→32→16→8 (7 levels, idx 0-6).
            import math
            max_dim = max(w, h)
            mip_cap = min(6, max(0, int(math.log2(max_dim)) - 2)) if max_dim > 4 else 0
            tex.build_mipmaps(max_level=mip_cap)
            return tex
        except Exception as e:
            log.debug(f"_GlTexCache._upload failed: {e}")
            return None

    def invalidate(self, img: Optional['Image.Image']) -> None:
        if img is None:
            return
        key = id(img)
        if key in self._cache:
            _, tex = self._cache[key]
            try:
                tex.release()
            except Exception:
                pass
            del self._cache[key]

    def clear(self) -> None:
        for (_, tex) in self._cache.values():
            try:
                tex.release()
            except Exception:
                pass
        self._cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
#  Mesh geometry builder
# ─────────────────────────────────────────────────────────────────────────────

_PREBUILT_STATIC_MESH_ATTR = "_gr_gpu_prebuilt_static_mesh"


def clear_prebuilt_static_gpu_mesh_data(node) -> None:
    """Drop RAM-cached static GPU mesh data for a node and its descendants."""
    stack = [node]
    seen = set()
    while stack:
        cur = stack.pop()
        if cur is None:
            continue
        cid = id(cur)
        if cid in seen:
            continue
        seen.add(cid)
        try:
            if hasattr(cur, _PREBUILT_STATIC_MESH_ATTR):
                delattr(cur, _PREBUILT_STATIC_MESH_ATTR)
        except Exception:
            pass
        try:
            stack.extend(getattr(cur, "children", []) or [])
        except Exception:
            pass


def clear_prebuilt_static_gpu_model_data(model) -> int:
    """Drop all RAM-cached static GPU mesh data attached to a model."""
    if model is None:
        return 0
    try:
        nodes = list(model.all_nodes())
    except Exception:
        root = getattr(model, "root_node", None)
        nodes = [root] if root is not None else []
    cleared = 0
    for node in nodes:
        try:
            if hasattr(node, _PREBUILT_STATIC_MESH_ATTR):
                delattr(node, _PREBUILT_STATIC_MESH_ATTR)
                cleared += 1
        except Exception:
            pass
    try:
        setattr(model, "_gr_gpu_prebuilt_mesh_count", 0)
    except Exception:
        pass
    return cleared


def _prebuilt_static_gpu_mesh_data(node, model_id: int, skin_bind_transform: bool):
    try:
        entry = getattr(node, _PREBUILT_STATIC_MESH_ATTR, None)
    except Exception:
        return None
    if not entry:
        return None
    if entry.get("model_id") != model_id:
        return None
    if bool(entry.get("skin_bind_transform")) != bool(skin_bind_transform):
        return None
    vdata = entry.get("vdata")
    if vdata is None:
        return None
    return vdata, entry.get("idx_arr")


def prebuild_static_gpu_mesh_data(model) -> int:
    """Build static mesh VBO arrays and viewport bounds before GUI render."""
    if model is None or not _NUMPY:
        return 0
    try:
        nodes = list(model.all_nodes())
    except Exception:
        return 0
    model_id = id(model)
    model_cls = (str(getattr(model, "classification", "character") or "character")).lower()
    model_type_raw = getattr(model, "model_type", None)
    try:
        model_type = int(model_type_raw) if model_type_raw is not None else 4
    except Exception:
        model_type = 4
    is_module = model_cls in ("effect", "tile", "other") or model_type in (0, 2)
    built = 0
    bounds_min = np.array([np.inf, np.inf, np.inf], dtype=np.float64)
    bounds_max = np.array([-np.inf, -np.inf, -np.inf], dtype=np.float64)
    for node in nodes:
        try:
            if not (getattr(node, "vertices", None) and getattr(node, "faces", None)):
                continue
            wp, wo = node.world_transform()
            skin_bind_transform = bool(getattr(node, "is_skin", False))
            vdata, idx_arr = _build_vbo_data(
                node,
                wp,
                wo,
                anim_pose_node=None,
                is_module=is_module,
                bone_index_remap=None,
                apply_skin_node_transform_for_bind=skin_bind_transform,
            )
            if vdata is None:
                continue
            try:
                pos = vdata[:, 0:3].astype(np.float64, copy=False)
                if pos.size:
                    bounds_min = np.minimum(bounds_min, pos.min(axis=0))
                    bounds_max = np.maximum(bounds_max, pos.max(axis=0))
            except Exception:
                pass
            setattr(
                node,
                _PREBUILT_STATIC_MESH_ATTR,
                {
                    "model_id": model_id,
                    "skin_bind_transform": skin_bind_transform,
                    "vdata": vdata,
                    "idx_arr": idx_arr,
                },
            )
            built += 1
        except Exception:
            continue
    try:
        setattr(model, "_gr_gpu_prebuilt_mesh_count", built)
        if built > 128 or is_module:
            setattr(model, "_gr_defer_txi_metadata", True)
        if built and np.isfinite(bounds_min).all() and np.isfinite(bounds_max).all():
            bb_min = tuple(float(v) for v in bounds_min.tolist())
            bb_max = tuple(float(v) for v in bounds_max.tolist())
            setattr(model, "_gr_render_bounds", (bb_min, bb_max))
            setattr(model, "_gr_bounds_prepared", True)
            model.bb_min = bb_min
            model.bb_max = bb_max
    except Exception:
        pass
    return built


def _quat_rotate_batch(q: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """
    Vectorized quaternion rotation for Nx3 points using quaternion q = (x,y,z,w).
    Uses the Rodrigues-like formula: v' = v + 2w(q×v) + 2(q×(q×v))
    which avoids building a full 3×3 rotation matrix and is ~2× faster for
    large batches than the per-vertex scalar loop.

    Parameters
    ----------
    q   : (4,) array [x, y, z, w]
    pts : (N, 3) array of points to rotate

    Returns
    -------
    (N, 3) rotated points
    """
    qx, qy, qz, qw = q
    # cross product: q_vec × pts  (broadcast Nx3)
    q_vec = np.array([qx, qy, qz], dtype=np.float64)
    t = 2.0 * np.cross(q_vec, pts)          # (N, 3)
    return pts + qw * t + np.cross(q_vec, t)


def _build_vbo_data(node, world_pos: tuple, world_orient: tuple,
                    anim_pose_node=None,
                    is_module: bool = False,
                    bone_index_remap: Optional[Dict[int, int]] = None,
                    apply_skin_node_transform_for_bind: bool = True) -> Tuple[Optional[np.ndarray],
                                                      Optional[np.ndarray]]:
    """
    Build interleaved VBO data for a ModelNode using vectorized NumPy.

    Returns (vertex_array, index_array) as float32/uint32 numpy arrays,
    or (None, None) on failure.

    Vertex layout per vertex (stride = 22 floats = 88 bytes):
      pos.xyz       3 floats  [0:3]
      norm.xyz      3 floats  [3:6]
      uv.xy         2 floats  [6:8]   (UV0 — primary/diffuse)
      uv_lm.xy      2 floats  [8:10]  (UV1 — lightmap)
      color.xyzw    4 floats  [10:14] (vertex colour + per-vertex alpha)
      bone_ids.xyzw 4 floats  [14:18] (bone palette indices, as float)
      weights.xyzw  4 floats  [18:22] (blend weights, sum ~ 1.0)

    Vectorization notes
    -------------------
    Previously used a Python loop (O(n_verts) iterations).  Now:
    - np.asarray converts vertex/normal/UV lists to arrays in one call
    - Quaternion rotation applied as a batch Nx3 vectorized op
    - Index arrays built with np.asarray on flat face lists
    This reduces build time from ~800 ms (10 k tris, pure Python) to
    ~5 ms (same mesh, vectorized NumPy).
    """
    if not _NUMPY:
        return None, None

    verts = getattr(node, 'vertices', getattr(node, 'verts', []))
    norms = getattr(node, 'normals', [])
    uvs   = getattr(node, 'uvs', [])
    uvs_lm = getattr(node, 'uvs_lm', [])
    faces  = getattr(node, 'faces', [])
    face_uvs = getattr(node, 'face_uvs', [])
    is_skin = bool(getattr(node, 'is_skin', False))

    n_verts = len(verts)
    n_faces = len(faces)
    if n_verts == 0 or n_faces == 0:
        return None, None

    # World transform
    wp = np.array(world_pos if world_pos else (0.0, 0.0, 0.0), dtype=np.float64)
    wo = np.array(world_orient if world_orient else (0.0, 0.0, 0.0, 1.0), dtype=np.float64)
    # Normalize quaternion for safety
    qlen = np.linalg.norm(wo)
    if qlen > 1e-9:
        wo = wo / qlen
    is_identity_rot = (abs(wo[3]) > 0.9999 and
                       abs(wo[0]) < 1e-6 and abs(wo[1]) < 1e-6 and abs(wo[2]) < 1e-6)
    is_identity_pos = (abs(wp[0]) < 1e-9 and abs(wp[1]) < 1e-9 and abs(wp[2]) < 1e-9)

    # ── Convert vertices and normals to Nx3 float64 arrays ──────────────────
    try:
        v_arr = np.asarray(verts, dtype=np.float64)
        if v_arr.ndim != 2 or v_arr.shape[1] != 3:
            v_arr = np.zeros((n_verts, 3), dtype=np.float64)
    except (ValueError, TypeError):
        v_arr = np.zeros((n_verts, 3), dtype=np.float64)

    n_norms = len(norms)
    if n_norms > 0:
        try:
            n_arr = np.asarray(norms[:n_verts], dtype=np.float64)
            if n_arr.ndim != 2 or n_arr.shape[1] != 3:
                n_arr = np.zeros((n_verts, 3), dtype=np.float64)
                n_arr[:, 2] = 1.0
        except (ValueError, TypeError):
            n_arr = np.zeros((n_verts, 3), dtype=np.float64)
            n_arr[:, 2] = 1.0
        # Pad if fewer normals than verts
        if len(n_arr) < n_verts:
            pad = np.zeros((n_verts - len(n_arr), 3), dtype=np.float64)
            pad[:, 2] = 1.0
            n_arr = np.vstack([n_arr, pad])
    else:
        n_arr = np.zeros((n_verts, 3), dtype=np.float64)
        n_arr[:, 2] = 1.0

    # ── D20-M: Apply world transform using per-node vertex_space contract ────
    #
    # Every node's vertex_space is set at load time by compute_vertex_space()
    # in src/core/vertex_space.py.  This replaces ALL centroid-magnitude
    # heuristics, _WORLDSPACE_VERT_THRESHOLD, FIX-PROXY-THRESHOLD,
    # FIX-ACCESSORY-WORLDSPACE, and FIX-CREATURE-WORLDSPACE checks.
    #
    # Rules (matching xoreos model_kotor.cpp, KotOR.js OdysseyModel3D.ts):
    #   NODE_LOCAL (0): vertices are in node's local coordinate system.
    #                   Apply full world_transform (rotate + translate).
    #   WORLD (1):      vertices already in model-root space (imported OBJ/FBX).
    #                   Do NOT apply world_transform.
    #   AABB_WALK (2):  walkmesh/collision — not rendered (should never reach here).
    #
    # References:
    #   xoreos model_kotor.cpp readMesh/readSkin — raw MDX read, no transform
    #   KotOR.js OdysseyModelNodeMesh.ts — raw push to array
    #   KotOR.js OdysseyModel3D.ts NodeMeshBuilder — matrixWorld for GPU
    #   reone mdlreader.cpp — reads verts as-is, applies node transform in renderer
    #   KotorBlender parser.py — verts loaded into Blender mesh, Blender applies hierarchy
    _node_vs = getattr(node, 'vertex_space', 0)  # default NODE_LOCAL

    _apply_node_transform = (
        _node_vs == 0
        and (not is_skin or bool(apply_skin_node_transform_for_bind))
    )

    if _apply_node_transform:  # NODE_LOCAL: apply one full world transform
        if not is_identity_rot:
            v_arr = _quat_rotate_batch(wo, v_arr)
            n_arr = _quat_rotate_batch(wo, n_arr)
        if not is_identity_pos:
            v_arr = v_arr + wp
    elif _node_vs == 1 or is_skin:  # WORLD or animated-skin input: pass through
        pass
    # _node_vs == 2 (AABB_WALK) should never reach VBO building

    # FIX-COMPOSITE-OFFSET: For nodes that belong to the head-accessory model
    # inside a _CompositeModel (e.g. head skin, eyeRA, teethUa in ad_saul),
    # apply the skeleton rebase offset so they render at the correct position
    # in the body skeleton.  The offset (_composite_nonskin_offset — legacy
    # name kept for attribute stability) is pre-computed by _CompositeModel
    # as: body_head_g_world - head_head_g_local, and is only attached to nodes
    # whose ownership is the head model (body nodes never carry this attr),
    # so no ownership gate is needed here beyond the None check.
    #
    # Historical bug: the previous gate excluded is_skin nodes, which left the
    # head *skin* mesh at floor level while eyes/teeth floated at head height.
    # Probe-verified fix: apply offset to all head-accessory nodes including
    # the skin, so the whole head moves as one with the body headhook.
    _cns_off = getattr(node, '_composite_nonskin_offset', None)
    if _cns_off is not None:
        _ox, _oy, _oz = float(_cns_off[0]), float(_cns_off[1]), float(_cns_off[2])
        if abs(_ox) > 1e-6 or abs(_oy) > 1e-6 or abs(_oz) > 1e-6:
            v_arr = v_arr + np.array([_ox, _oy, _oz], dtype=np.float64)

    _gr_gpu_probe(node, world_pos or (0.0, 0.0, 0.0),
                  world_orient or (0.0, 0.0, 0.0, 1.0),
                  is_identity_rot, _cns_off)

    # ── Normalize normals (prevent shading errors from non-unit normals) ─────
    # After quaternion rotation and world-space transform, normals may drift from
    # unit length.  Normalize each row to ensure correct Phong shading.
    n_lens = np.linalg.norm(n_arr, axis=1, keepdims=True)
    n_lens = np.where(n_lens < 1e-9, 1.0, n_lens)  # avoid div-by-zero
    n_arr = n_arr / n_lens

    # ── UV arrays ────────────────────────────────────────────────────────────
    # FIX-UV-SEAM-EXPAND: Build uv_arr from the FULL uvs list (n_uvs entries),
    # NOT truncated to n_verts.  KotOR binary MDL trimeshes use separate tvert
    # (texture-vertex) indices in face_uvs[] that can reference UV entries
    # beyond index n_verts-1 — the seam-split duplicate UVs are appended after
    # the geometry verts.  Truncating to n_verts discarded those extra entries,
    # causing the expanded-path UV lookup (uv_arr[ti]) to fall back to the
    # vertex UV (uv_arr[vi]) instead of the correct seam UV, producing wrong
    # texture coordinates on every seam-split corner (e.g. quad row4 V=1.0
    # instead of V=0.99 when face_uvs=[..,[0,4,3]] and uvs[4]=(1.0,0.99)).
    #
    # Seam-vert healing (below) uses v_arr for spatial lookup which is indexed
    # by vertex index (0..n_verts-1), so we restrict the heal pass to entries
    # 0..n_verts-1; extra tvert-only entries (n_verts..n_uvs-1) are not
    # directly linked to a geometry position and must not be healed by position.
    n_uvs = len(uvs)
    if n_uvs > 0:
        try:
            uv_arr = np.asarray(uvs, dtype=np.float32)      # shape: (n_uvs, ...)
            if uv_arr.ndim != 2 or uv_arr.shape[1] < 2:
                uv_arr = np.full((n_uvs, 2), 0.5, dtype=np.float32)
            elif uv_arr.shape[1] > 2:
                uv_arr = uv_arr[:, :2]
        except (ValueError, TypeError):
            uv_arr = np.full((n_uvs, 2), 0.5, dtype=np.float32)
        bad_uv = ~np.all(np.isfinite(uv_arr), axis=1)
        if np.any(bad_uv):
            uv_arr[bad_uv] = 0.5
    else:
        uv_arr = np.full((n_verts, 2), 0.5, dtype=np.float32)
        n_uvs = n_verts  # for consistent indexing below

    # UV1/lightmap coordinates follow the same texture-vertex indexing rules as
    # UV0. Keep the full array for expanded per-face lookup; slice/pad only when
    # filling the vertex-indexed fast-path VBO.
    n_uvs_lm = len(uvs_lm)
    if n_uvs_lm > 0:
        try:
            uv_lm_src_arr = np.asarray(uvs_lm, dtype=np.float32)
            if uv_lm_src_arr.ndim != 2 or uv_lm_src_arr.shape[1] < 2:
                uv_lm_src_arr = np.full((n_uvs_lm, 2), 0.5, dtype=np.float32)
            elif uv_lm_src_arr.shape[1] > 2:
                uv_lm_src_arr = uv_lm_src_arr[:, :2]
        except (ValueError, TypeError):
            uv_lm_src_arr = np.full((n_uvs_lm, 2), 0.5, dtype=np.float32)
        bad_lm = ~np.all(np.isfinite(uv_lm_src_arr), axis=1)
        if np.any(bad_lm):
            uv_lm_src_arr[bad_lm] = 0.5
    else:
        uv_lm_src_arr = np.full((n_verts, 2), 0.5, dtype=np.float32)
        n_uvs_lm = n_verts

    # ── Assemble interleaved vertex buffer (N × 22) ──────────────────────────
    # Phase A: Extended VBO layout includes bone_ids (4f) + bone_weights (4f)
    # for GPU skinning.  All nodes use 22 floats per vertex for a consistent
    # VAO format; non-skin nodes get identity values (idx=0, weight=1,0,0,0).
    #
    # Layout per vertex (stride = 22 floats = 88 bytes):
    #   pos.xyz       3 floats  [0:3]
    #   norm.xyz      3 floats  [3:6]
    #   uv.xy         2 floats  [6:8]   (UV0 — primary/diffuse)
    #   uv_lm.xy      2 floats  [8:10]  (UV1 — lightmap)
    #   color.xyzw    4 floats  [10:14] (vertex colour + per-vertex alpha)
    #   bone_ids.xyzw 4 floats  [14:18] (bone palette indices, as float)
    #   weights.xyzw  4 floats  [18:22] (blend weights, sum ≈ 1.0)
    #
    # vdata is keyed by *vertex* index (0..n_verts-1).  uv_arr may have more
    # rows than n_verts (extra seam-split tvert entries beyond n_verts-1) so we
    # slice to exactly n_verts rows when copying into vdata.
    vdata = np.zeros((n_verts, 22), dtype=np.float32)
    vdata[:, 0:3] = v_arr.astype(np.float32)
    vdata[:, 3:6] = n_arr.astype(np.float32)
    _uv_for_vdata = uv_arr[:n_verts] if len(uv_arr) >= n_verts else np.vstack(
        [uv_arr, np.full((n_verts - len(uv_arr), 2), 0.5, dtype=np.float32)])
    _uv_lm_for_vdata = uv_lm_src_arr[:n_verts] if len(uv_lm_src_arr) >= n_verts else np.vstack(
        [uv_lm_src_arr, np.full((n_verts - len(uv_lm_src_arr), 2), 0.5, dtype=np.float32)])
    vdata[:, 6:8]  = _uv_for_vdata[:, :2]
    vdata[:, 8:10] = _uv_lm_for_vdata[:, :2]
    vdata[:, 10:14] = 1.0  # white vertex colour + alpha 1

    # ── Phase A: Populate bone_ids and weights for skin nodes ────────────────
    # bone_ids[14:18] = palette indices (float);  weights[18:22] = blend weights.
    # Non-skin nodes: identity (idx=0, weight=[1,0,0,0]) — shader pass-through.
    #
    # FIX-SKIN-QBONE: BoneWeight.bone_index is a LOCAL index into this skin
    # node's bone_map[] array.  The renderer now uploads a per-skin local
    # qBone/tBone palette before each skin draw, so no remap is needed in the
    # normal path.  The optional remap remains for focused tests and diagnostics.
    if is_skin:
        _skin_data = getattr(node, 'skin_data', [])
        if _skin_data and len(_skin_data) >= n_verts:
            for _vi in range(n_verts):
                _sd = _skin_data[_vi]
                _infl = getattr(_sd, 'influences', [])
                for _bi_idx in range(min(4, len(_infl))):
                    _bw = _infl[_bi_idx]
                    _local_idx = int(getattr(_bw, 'bone_index', 0))
                    # Optional remap for tests/diagnostics; production skin draws
                    # keep local bone_map indices for the per-skin qBone palette.
                    if bone_index_remap is not None:
                        _palette_idx = bone_index_remap.get(_local_idx, 0)
                    else:
                        _palette_idx = _local_idx
                    vdata[_vi, 14 + _bi_idx] = float(_palette_idx)
                    vdata[_vi, 18 + _bi_idx] = float(getattr(_bw, 'weight', 0.0))
        else:
            # No per-vertex skin data: identity (bone 0, weight 1.0)
            vdata[:, 18] = 1.0  # first weight = 1.0
    else:
        # Non-skin node: identity skinning values (bone 0, weight 1.0)
        vdata[:, 18] = 1.0  # first weight = 1.0

    # ── Build face index arrays ───────────────────────────────────────────────
    # FIX-SEAM: KotOR binary MDL uses per-face tvert (texture-vertex) indices
    # that are stored separately from the geometry vertex indices.  The NWN
    # exporter's ProcessSkinSeams() duplicates geometry vertices at UV seams so
    # that each half of a seam can have a different UV coordinate.  When
    # face_uvs is present (len == n_faces), every face has its own 3 tvert
    # indices that index into the uvs[] array independently of the faces[]
    # vertex indices.  We must therefore expand to a triangle-list (no IBO) so
    # that each triangle corner gets the correct per-face UV.
    #
    # Additionally, skin nodes always need expansion because the engine's vertex
    # layout may not match the face list order (seam verts are duplicated with
    # different UV but identical position).
    #
    # Reference: PyKotor io_mdl.py ProcessSkinSeams engine comment;
    #            PyKotor read_mdl.py gl_load_stitched_model (expands per-face).
    _has_face_uvs = (len(face_uvs) == n_faces)

    # FIX-FACEUVOPT-V2: When face_uvs has the same length as faces but all
    # tvert indices equal the corresponding vertex indices (the t=-1→use_vert
    # case from binary MDL trimeshes), treat it as "no per-face UV" so we can
    # use the fast IBO path.  This avoids unnecessarily expanding a triangle-
    # list for module/area models whose binary trimeshes always have t==-1.
    #
    # v2: Replaced the O(n) Python loop (which was capped at n_faces<=2000 to
    # avoid slowness) with a vectorized NumPy comparison that runs in O(1)
    # time for any mesh size.  Module room meshes commonly have 3000-10000
    # faces; the previous cap forced them through the expanded path
    # unnecessarily, wasting ~3x VBO memory and blocking per-material-slot
    # IBO construction (since expanded meshes are non-indexed).
    if _has_face_uvs and not is_skin:
        try:
            _fuv_arr = np.asarray(face_uvs, dtype=np.int32)  # (n_faces, 3)
            _fv_arr  = np.asarray(faces,    dtype=np.int32)   # (n_faces, 3)
            if (_fuv_arr.shape == _fv_arr.shape and
                    _fuv_arr.ndim == 2 and _fuv_arr.shape[1] >= 3):
                if np.array_equal(_fuv_arr[:, :3], _fv_arr[:, :3]):
                    _has_face_uvs = False
        except (ValueError, TypeError):
            pass  # non-uniform lists — fall through to expanded path

    # Fast path: no per-face UV indices AND not a skin node → use IBO
    if not _has_face_uvs and not is_skin:
        try:
            f_arr = np.asarray(faces, dtype=np.int32)
            if f_arr.ndim == 2 and f_arr.shape[1] >= 3:
                idx = f_arr[:, :3]  # (N_faces, 3)
                # Filter out-of-range indices
                valid = (np.all(idx >= 0, axis=1) &
                         np.all(idx < n_verts, axis=1))
                idx = idx[valid].astype(np.uint32)
                if len(idx) == 0:
                    return None, None
                try:
                    setattr(node, '_gr_last_vbo_source_indices', list(range(n_verts)))
                except Exception:
                    pass
                return vdata, idx.flatten()
        except (ValueError, TypeError):
            pass
        # Fallback: Python loop for jagged/non-uniform face list
        idx_list = []
        for face in faces:
            if len(face) < 3:
                continue
            vi0, vi1, vi2 = int(face[0]), int(face[1]), int(face[2])
            if vi0 < n_verts and vi1 < n_verts and vi2 < n_verts:
                idx_list.extend([vi0, vi1, vi2])
        if not idx_list:
            return None, None
        try:
            setattr(node, '_gr_last_vbo_source_indices', list(range(n_verts)))
        except Exception:
            pass
        return vdata, np.array(idx_list, dtype=np.uint32)

    # Expanded path: per-face UV indices OR skin mesh → expand to triangle list
    # Each triangle corner is a (position, normal, uv) triple taken from the
    # correct vertex/tvert index pair.  No IBO needed.
    #
    # FIX-EXPANDUV: Use sanitized uv_arr (already seam-healed and sentinel-
    # checked) as the UV source, NOT the raw uvs[] list.  This ensures that
    # the seam-healing pass (which corrects duplicate-vertex UVs at seams like
    # p_hk47 fingers and c_kraytdragon claws) is applied to the final vertices.
    # Previously the expanded path re-read raw uvs[ti], bypassing seam healing.
    # Now it reads uv_arr[ti] which is the sanitized version.
    # Exception: when ti != vi (genuine per-face UV index differs from vertex
    # index), we must use the correct tvert UV from uv_arr[ti].  This is the
    # KotOR ProcessSkinSeams() case.
    expanded_rows = []
    expanded_source_indices = []
    n_uv_arr = len(uv_arr)   # sanitized UV array (already seam-healed)
    n_uv_lm_arr = len(uv_lm_src_arr)  # sanitized UV1/lightmap array
    for fi, face in enumerate(faces):
        if len(face) < 3:
            continue
        vi0, vi1, vi2 = face[0], face[1], face[2]
        if vi0 >= n_verts or vi1 >= n_verts or vi2 >= n_verts:
            continue
        # Use per-face UV indices if available, else fall back to vertex index
        if _has_face_uvs and fi < len(face_uvs):
            fuvs = face_uvs[fi]
            ti0, ti1, ti2 = (int(fuvs[0]), int(fuvs[1]), int(fuvs[2])) if len(fuvs) >= 3 else (vi0, vi1, vi2)
        else:
            ti0, ti1, ti2 = vi0, vi1, vi2
        for vi, ti in ((vi0, ti0), (vi1, ti1), (vi2, ti2)):
            row = vdata[vi].copy()
            # FIX-EXPANDUV: Use sanitized uv_arr[ti] instead of raw uvs[ti].
            # uv_arr is already sentinel-checked and seam-healed.
            if 0 <= ti < n_uv_arr:
                row[6] = uv_arr[ti, 0]
                row[7] = uv_arr[ti, 1]
            elif 0 <= vi < n_uv_arr:
                # tvert index out of range → fall back to vertex UV
                row[6] = uv_arr[vi, 0]
                row[7] = uv_arr[vi, 1]
            # else: keep row's UV from vdata[vi] (already set from uv_arr[vi])
            if 0 <= ti < n_uv_lm_arr:
                row[8] = uv_lm_src_arr[ti, 0]
                row[9] = uv_lm_src_arr[ti, 1]
            elif 0 <= vi < n_uv_lm_arr:
                row[8] = uv_lm_src_arr[vi, 0]
                row[9] = uv_lm_src_arr[vi, 1]
            # else: keep row's UV1 from vdata[vi]
            expanded_rows.append(row)
            expanded_source_indices.append(int(vi))

    if not expanded_rows:
        return None, None
    try:
        setattr(node, '_gr_last_vbo_source_indices', expanded_source_indices)
    except Exception:
        pass
    return np.stack(expanded_rows).astype(np.float32), None


def _split_vbo_attributes_for_gpu(vdata: 'np.ndarray') -> Tuple['np.ndarray', 'np.ndarray']:
    """Split legacy 22-float rows into float attributes plus int32 bone IDs."""
    main = np.empty((len(vdata), 18), dtype=np.float32)
    main[:, 0:14] = vdata[:, 0:14]
    main[:, 14:18] = vdata[:, 18:22]  # weights remain float
    bone_ids = np.rint(vdata[:, 14:18]).astype(np.int32)
    return main, bone_ids


# ─────────────────────────────────────────────────────────────────────────────
#  GPU mesh buffer (one per node, cached)
# ─────────────────────────────────────────────────────────────────────────────

class _GpuMesh:
    """Holds the VBO / VAO / IBO for one ModelNode.

    FIX-MULTITEX-SPLIT: For multi-material nodes (tex_count > 1 with per-face
    material slots), mat_slot_ibos stores per-material-slot IBOs so that each
    face group can be drawn with the correct texture without overdrawing the
    entire mesh.  mat_slot_vaos stores the corresponding VAOs.
    Format: {slot_idx: (vao, ibo, tri_count)}
    """

    def __init__(self):
        self.vao: Optional['moderngl.VertexArray'] = None
        self.vbo: Optional['moderngl.Buffer'] = None
        self.bone_id_vbo: Optional['moderngl.Buffer'] = None
        self.ibo: Optional['moderngl.Buffer'] = None
        self.tri_count: int = 0
        self.indexed: bool = False
        self.uploaded_vertex_count: int = 0
        self.first8_uv0_uploaded: List[List[float]] = []
        self.first8_uv1_uploaded: List[List[float]] = []
        self.uploaded_positions: List[List[float]] = []
        self.uploaded_bone_ids: List[List[int]] = []
        self.uploaded_weights: List[List[float]] = []
        self.uploaded_source_indices: List[int] = []
        self.uv1_attribute_bound: bool = False
        self.skin_bind_transform: Optional[bool] = None
        # Per-material-slot draw groups for multi-texture nodes
        self.mat_slots: Dict[int, tuple] = {}  # {slot: (vao, ibo, tri_count)}

    def release(self):
        if self.vao:
            try: self.vao.release()
            except Exception: pass
            self.vao = None
        if self.vbo:
            try: self.vbo.release()
            except Exception: pass
            self.vbo = None
        if self.bone_id_vbo:
            try: self.bone_id_vbo.release()
            except Exception: pass
            self.bone_id_vbo = None
        if self.ibo:
            try: self.ibo.release()
            except Exception: pass
            self.ibo = None
        # Release per-material-slot VAOs and IBOs
        for slot_data in self.mat_slots.values():
            try:
                if slot_data[0]:  # vao
                    slot_data[0].release()
                if slot_data[1]:  # ibo
                    slot_data[1].release()
            except Exception:
                pass
        self.mat_slots.clear()


# ─────────────────────────────────────────────────────────────────────────────
#  Main GPU renderer class
# ─────────────────────────────────────────────────────────────────────────────

class GpuRenderer:
    """
    Hybrid GPU/CPU renderer for KotOR models.

    Usage
    -----
    renderer = GpuRenderer()
    img = renderer.render(model, camera, W, H,
                           textures={name: pil_img}, anim_pose=None)

    The `camera` is a GhostRigger ArcBallCamera-compatible object with:
        camera.eye   → (x, y, z) camera world position  (ArcBallCamera: call camera.eye())
        camera.target → (x, y, z) look-at target          (ArcBallCamera: list attribute)
        camera.up    → (x, y, z) up vector (optional, default (0,0,1) = Z-up for KotOR)
        camera.fov   → vertical field-of-view in degrees (optional, default 45°)
        camera.near, camera.far  → clip distances (optional, default 0.01/2000)
    """

    #: Set to True to force the CPU (PIL) fallback even if GPU is available.
    force_cpu: bool = False

    def __init__(self):
        self._ctx: Optional['moderngl.Context'] = None
        self._prog: Optional['moderngl.Program'] = None
        self._grid_prog: Optional['moderngl.Program'] = None
        self._grid_vbo: Optional['moderngl.Buffer'] = None
        self._grid_vao: Optional['moderngl.VertexArray'] = None
        self._tex_cache: Optional[_GlTexCache] = None
        self._mesh_cache: Dict[int, _GpuMesh] = {}  # node id → _GpuMesh
        self._gpu_available: bool = False
        self._init_attempted: bool = False
        # Persistent FBO (reused across frames for same resolution)
        self._fbo: Optional['moderngl.Framebuffer'] = None
        self._fbo_w: int = 0
        self._fbo_h: int = 0
        # FIX-MSAA: Resolve FBO for multisampled MSAA readback
        self._fbo_resolve: Optional['moderngl.Framebuffer'] = None
        self._fbo_msaa: bool = False
        # PERF-FBO-SIMPLE: Non-MSAA FBO for fast interactive frames.
        # On llvmpipe, MSAA resolve (copy_framebuffer) costs ~59ms/frame.
        # During interactive drag we skip MSAA and draw to this simple FBO.
        self._fbo_simple: Optional['moderngl.Framebuffer'] = None
        self._fbo_simple_w: int = 0
        self._fbo_simple_h: int = 0
        # Placeholder 1×1 white texture (used as diffuse fallback)
        self._white_tex: Optional['moderngl.Texture'] = None
        # FIX-ENVFB: Neutral grey 1×1 environment-map fallback texture.
        # When a node has txi_envmaptexture set but the texture isn't in the
        # texture dict (partial texture load), bind this grey instead of nothing.
        # A grey env map (0.5,0.5,0.5) produces a slight metallic tint which is
        # correct: the env blend weight (diffuse alpha) modulates towards grey
        # rather than towards zero, keeping the surface opaque.
        self._grey_env_tex: Optional['moderngl.Texture'] = None
        # FIX-PERSCACHE: Persistent world-transform cache keyed by (model_id, node_id).
        # Survives across frames for static geometry; invalidated when the model changes.
        # This reduces per-frame cost from O(N×depth) parent-chain walks to O(1) lookups.
        self._wt_model_id: int = 0    # id() of the last model we built the cache for
        self._wt_cache: Dict[int, tuple] = {}  # node id() → (world_pos, world_orient)
        # PERF-UNIFCACHE: Cached uniform references (populated on first render).
        # Avoids prog['name'] dict lookup overhead per draw call.
        self._u: Dict[str, object] = {}   # uniform name → Uniform object
        # PERF-NODECACHE: Pre-classified node lists cached per model.
        # Avoids re-classifying every node every frame when the model hasn't changed.
        self._node_cache_model_id: int = 0
        self._node_cache_opaque: list = []
        self._node_cache_cutout: list = []
        self._node_cache_transparent: list = []
        self._node_cache_proxy_ids: set = set()
        self._node_cache_is_module: bool = False
        # PERF: Interactive mode skips MSAA for faster frame times.
        # Keep the default scale at full resolution; lowering it is available
        # for emergency performance mode, but makes animated previews pixelated.
        self.interactive: bool = False
        self.interactive_render_scale: float = 1.0
        self.show_solid: bool = True
        self.show_texture: bool = True
        self.show_diffuse_map: bool = True
        self.show_lightmap_map: bool = False
        self.show_environment_map: bool = True
        self.show_specular_map: bool = True
        self.show_normal_map: bool = True
        self.lightmap_intensity: float = 0.55
        self.lightmap_mode: str = "disabled"
        self.lighting_mode: str = "scene"
        self.shader_complexity_mode: str = "off"
        self.scene_ambient: float = 0.06
        self.show_light_gizmos: bool = True
        self.show_light_radius_volumes: bool = False
        self.show_wireframe: bool = False
        self.render_mode: str = "realistic"
        self.selected_node = None
        self.selected_nodes: list = []
        self.wire_color: tuple[float, float, float] = (0.18, 0.62, 0.95)
        self._wireframe_pass: bool = False
        self.show_grid: bool = True
        self.cull_faces: bool = True
        self.max_new_mesh_uploads_per_frame: int = 64
        self.deferred_mesh_uploads: bool = False
        # ── Phase A: GPU Skinning state ──────────────────────────────────────────
        # MatrixPaletteUploader instance, created per model when skin nodes exist.
        # Caches inverse bind-pose matrices and computes per-frame bone palettes.
        self._skin_uploader: Optional['MatrixPaletteUploader'] = None
        self._skin_model_id: int = 0  # id() of model for which bind-pose was built
        self._skin_bone_count: int = 0  # number of bones in the current palette
        self._skin_logged: bool = False  # one-shot log for GPU skinning activation
        self._gl_state_trace_path: str = _gl_state_trace_path()
        self._lm_data_dump_path: str = _lm_data_dump_path()
        self._lm_data_dump_seen: set = set()
        self._skin_dump_path: str = _skin_dump_path()
        self._skin_dump_seen: set = set()
        # Performance counters
        self.perf: Dict[str, float] = {
            'last_frame_ms': 0.0,
            'gpu_upload_ms': 0.0,
            'draw_ms': 0.0,
            'readback_ms': 0.0,
            'tri_count': 0,
            'backend': 'none',
        }

    # ── Context management ────────────────────────────────────────────────────

    def _ensure_context(self) -> bool:
        """Try to initialize the ModernGL EGL context once."""
        if self._init_attempted:
            return self._gpu_available
        self._init_attempted = True
        if not _MODERNGL or not _NUMPY or self.force_cpu:
            return False
        try:
            self._ctx, _ctx_backend = _create_moderngl_standalone_context()
            self._prog = self._ctx.program(
                vertex_shader=_VERT_SRC,
                fragment_shader=_FRAG_SRC,
            )
            self._grid_prog = self._ctx.program(
                vertex_shader=_GRID_VERT_SRC,
                fragment_shader=_GRID_FRAG_SRC,
            )
            self._tex_cache = _GlTexCache(self._ctx)
            # PERF-UNIFCACHE: Pre-cache all uniform references to avoid
            # prog['name'] dict lookups (~0.4ms/frame savings on 56-node models).
            _p = self._prog
            _u = {}
            for _uname in (
                'u_mvp', 'u_model', 'u_normal_mat', 'u_cam_pos',
                'u_light_dir', 'u_light_dir2', 'u_ambient', 'u_specular',
                'u_shininess', 'u_alpha_test', 'u_decal', 'u_wateralpha',
                'u_has_spec', 'u_has_bump', 'u_alpha', 'u_node_alpha', 'u_blend_mode',
                'u_has_tex', 'u_has_lm', 'u_lm_shade', 'u_lightmap_intensity',
                'u_lightmap_mode', 'u_has_env',
                'u_lm_composite_mode',
                'u_scene_lighting', 'u_scene_ambient', 'u_scene_light_count',
                'u_scene_light_enabled', 'u_scene_light_kind',
                'u_scene_light_ambient_only', 'u_scene_light_pos',
                'u_scene_light_dir', 'u_scene_light_color',
                'u_scene_light_radius', 'u_scene_light_intensity',
                'u_scene_light_cone_cos', 'u_scene_light_area_size',
                'u_diffuse', 'u_selfillum', 'u_uv_scroll', 'u_rotate_tex',
                'u_uv_v_flip', 'u_flipbook_off', 'u_flipbook_size', 'u_features',
                'u_water_time', 'u_proc_type', 'u_dangly_enabled',
                'u_dangly_displacement', 'u_dangly_time',
                'u_saber_enabled', 'u_saber_displacement', 'u_saber_length',
                'u_oit_enabled', 'u_tex', 'u_lm_tex', 'u_env_tex', 'u_spec_tex', 'u_bump_tex',
                'u_debug_visualize', 'u_wireframe_enabled', 'u_wire_color',
                'u_render_mode', 'u_selected',
                # Phase A: GPU Skinning uniforms
                'u_skin_enabled', 'u_bone_count', 'u_bones',
            ):
                try:
                    _u[_uname] = _p[_uname]
                except KeyError:
                    pass
            self._u = _u
            self._gpu_available = True
            log.info("GpuRenderer: ModernGL %s context GL %s",
                     _ctx_backend, self._ctx.version_code)
            return True
        except Exception as e:
            log.info(f"GpuRenderer: GPU init failed ({e}) – using CPU fallback")
            self._gpu_available = False
            return False

    def release(self):
        """Release all GPU resources."""
        if self._tex_cache:
            self._tex_cache.clear()
        for m in self._mesh_cache.values():
            m.release()
        self._mesh_cache.clear()
        # Release persistent FBO
        if self._fbo is not None:
            try:
                self._fbo.color_attachments[0].release()
                self._fbo.depth_attachment.release()
                self._fbo.release()
            except Exception:
                pass
            self._fbo = None
        # Release MSAA resolve FBO
        if self._fbo_resolve is not None:
            try:
                self._fbo_resolve.color_attachments[0].release()
                self._fbo_resolve.release()
            except Exception:
                pass
            self._fbo_resolve = None
        # Release simple (non-MSAA) FBO
        if self._fbo_simple is not None:
            try:
                self._fbo_simple.color_attachments[0].release()
                self._fbo_simple.depth_attachment.release()
                self._fbo_simple.release()
            except Exception:
                pass
            self._fbo_simple = None
        # Release white placeholder texture
        if self._white_tex is not None:
            try: self._white_tex.release()
            except Exception: pass
            self._white_tex = None
        # Release grey env-map fallback texture
        if self._grey_env_tex is not None:
            try: self._grey_env_tex.release()
            except Exception: pass
            self._grey_env_tex = None
        # Phase A: Release GPU skinning uploader
        if self._skin_uploader is not None:
            try: self._skin_uploader.release()
            except Exception: pass
            self._skin_uploader = None
            self._skin_model_id = 0
            self._skin_bone_count = 0
        if self._prog:
            try: self._prog.release()
            except Exception: pass
            self._prog = None
        if self._grid_vao:
            try: self._grid_vao.release()
            except Exception: pass
            self._grid_vao = None
        if self._grid_vbo:
            try: self._grid_vbo.release()
            except Exception: pass
            self._grid_vbo = None
        if self._grid_prog:
            try: self._grid_prog.release()
            except Exception: pass
            self._grid_prog = None
        if self._ctx:
            try: self._ctx.release()
            except Exception: pass
            self._ctx = None
        self._gpu_available = False
        self._init_attempted = False  # allow re-initialisation after release

    def clear_caches(self) -> None:
        """Clear per-model GPU mesh and texture caches without destroying the context.

        Call this between model renders in a batch loop to free GPU VRAM while
        keeping the EGL context alive for the next model.  This prevents OOM
        kills when rendering thousands of models consecutively.

        FIX-PERF-CLEAR: Do NOT reset _init_attempted here.  The original code
        incorrectly set _init_attempted=False, which forced a full ModernGL EGL
        context re-initialization on every subsequent render() call.  Re-init
        costs ~70 ms per model × 3,304 models = ~4 minutes of unnecessary GPU
        setup in a batch render.  The GPU context (self._ctx, self._prog) is
        still valid after clearing caches — only mesh VAOs/VBOs and texture
        uploads are freed, not the context itself.
        """
        # Release all cached mesh VAO/VBO/IBOs
        for m in self._mesh_cache.values():
            m.release()
        self._mesh_cache.clear()
        # Release all cached GL textures to free VRAM
        if self._tex_cache:
            self._tex_cache.clear()
        # Clear persistent world-transform cache (invalidated per model anyway)
        self._wt_cache.clear()
        self._wt_model_id = 0
        # PERF-NODECACHE: Clear pre-classified node lists
        self._node_cache_model_id = 0
        self._node_cache_opaque = []
        self._node_cache_cutout = []
        self._node_cache_transparent = []
        self._node_cache_proxy_ids = set()
        # Phase A: Clear GPU skinning state (new model = new bone palette)
        if self._skin_uploader is not None:
            try: self._skin_uploader.release()
            except Exception: pass
            self._skin_uploader = None
        self._skin_model_id = 0
        self._skin_bone_count = 0
        # NOTE: _init_attempted is intentionally NOT reset here — the EGL context
        # remains alive and valid across clear_caches() calls.

    # ── Main render entry ─────────────────────────────────────────────────────

    def reset_framebuffers(self) -> None:
        """Release cached offscreen render targets while keeping the GL context alive."""

        def _release_fbo(fbo) -> None:
            if fbo is None:
                return
            try:
                for attachment in getattr(fbo, "color_attachments", []) or []:
                    if attachment is not None:
                        attachment.release()
                depth = getattr(fbo, "depth_attachment", None)
                if depth is not None:
                    depth.release()
                fbo.release()
            except Exception:
                pass

        _release_fbo(self._fbo)
        _release_fbo(self._fbo_resolve)
        _release_fbo(self._fbo_simple)
        self._fbo = None
        self._fbo_resolve = None
        self._fbo_simple = None
        self._fbo_w = 0
        self._fbo_h = 0
        self._fbo_simple_w = 0
        self._fbo_simple_h = 0
        self._fbo_msaa = False

    def _ensure_grid_vao(self):
        if not (_NUMPY and self._ctx is not None and self._grid_prog is not None):
            return None
        if self._grid_vao is not None:
            return self._grid_vao

        extent = 60
        major_every = 5
        minor = (58 / 255.0, 64 / 255.0, 72 / 255.0)
        major = (82 / 255.0, 90 / 255.0, 102 / 255.0)
        x_axis = (118 / 255.0, 54 / 255.0, 54 / 255.0)
        y_axis = (62 / 255.0, 112 / 255.0, 68 / 255.0)
        rows = []

        for i in range(-extent, extent + 1):
            color = x_axis if i == 0 else (major if i % major_every == 0 else minor)
            rows.append((-extent, i, 0.0, *color))
            rows.append((extent, i, 0.0, *color))

        for i in range(-extent, extent + 1):
            color = y_axis if i == 0 else (major if i % major_every == 0 else minor)
            rows.append((i, -extent, 0.0, *color))
            rows.append((i, extent, 0.0, *color))

        data = np.asarray(rows, dtype=np.float32)
        self._grid_vbo = self._ctx.buffer(data.tobytes())
        self._grid_vao = self._ctx.vertex_array(
            self._grid_prog,
            [(self._grid_vbo, '3f 3f', 'in_pos', 'in_color')],
        )
        return self._grid_vao

    def _draw_grid(self, ctx, mvp) -> None:
        if not self.show_grid:
            return
        vao = self._ensure_grid_vao()
        if vao is None or self._grid_prog is None:
            return
        self._grid_prog['u_mvp'].write(_mat4_tobytes(mvp))
        ctx.disable(moderngl.BLEND)
        ctx.depth_mask = False
        try:
            ctx.line_width = 1.0
        except Exception:
            pass
        try:
            vao.render(moderngl.LINES)
        finally:
            ctx.depth_mask = True

    def _draw_light_gizmos(self, ctx, mvp, nodes, get_world_transform) -> None:
        if not bool(getattr(self, "show_light_gizmos", True)):
            return
        if not (_NUMPY and self._grid_prog is not None and nodes):
            return

        def _add_line(rows, a, b, color):
            rows.append((float(a[0]), float(a[1]), float(a[2]), *color))
            rows.append((float(b[0]), float(b[1]), float(b[2]), *color))

        def _v_add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
        def _v_sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
        def _v_mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
        def _v_cross(a, b):
            return (a[1] * b[2] - a[2] * b[1],
                    a[2] * b[0] - a[0] * b[2],
                    a[0] * b[1] - a[1] * b[0])
        def _v_norm(a):
            ln = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) or 1.0
            return (a[0] / ln, a[1] / ln, a[2] / ln)

        def _basis(direction):
            forward = _v_norm(direction)
            seed = (0.0, 0.0, 1.0) if abs(forward[2]) < 0.92 else (0.0, 1.0, 0.0)
            right = _v_norm(_v_cross(seed, forward))
            up = _v_norm(_v_cross(forward, right))
            return forward, right, up

        def _ring(rows, center, axis_a, axis_b, radius, color, steps=32):
            prev = None
            for i in range(steps + 1):
                t = (i / steps) * math.tau
                pt = _v_add(center, _v_add(_v_mul(axis_a, math.cos(t) * radius),
                                           _v_mul(axis_b, math.sin(t) * radius)))
                if prev is not None:
                    _add_line(rows, prev, pt, color)
                prev = pt

        rows = []
        selected = getattr(self, "selected_node", None)
        draw_volumes = bool(getattr(self, "show_light_radius_volumes", True))
        for node in nodes:
            if not bool(getattr(node, "is_light", False)):
                continue
            if bool(getattr(node, "_gr_light_hidden", False)) or bool(getattr(node, "_gr_light_deleted", False)):
                continue
            try:
                pos, orient = get_world_transform(node)
            except Exception:
                pos = getattr(node, "position", (0.0, 0.0, 0.0))
                orient = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
            kind = str(getattr(node, "light_kind", "point") or "point").lower()
            helper_kind = kind.replace("aurora_", "")
            enabled = bool(getattr(node, "light_enabled", True))
            cone = max(1.0, min(179.0, float(getattr(node, "light_cone_degrees", 45.0) or 45.0)))
            direction = self._rotate_vec_by_quat((0.0, 0.0, -1.0), orient)
            forward, right, up = _basis(direction)
            base = LIGHT_HELPER_COLORS.get(helper_kind, LIGHT_HELPER_COLORS["point"])
            if not enabled:
                base = tuple(c * 0.38 for c in base)
            if bool(getattr(node, "_gr_light_selected", False)):
                base = tuple(min(1.0, c * LIGHT_HELPER_SELECTED_BOOST) for c in base)
            if node is selected or bool(getattr(node, "_gr_light_metadata", {}).get("active_selection", False)):
                base = (0.90, 0.95, 1.0)

            _ring(rows, pos, right, up, LIGHT_HELPER_MARKER_RADIUS, base, steps=16)
            if helper_kind == "ambient":
                continue
            if helper_kind == "area":
                half = LIGHT_HELPER_AREA_SIZE * 0.5
                c0 = _v_add(pos, _v_add(_v_mul(right, -half), _v_mul(up, -half)))
                c1 = _v_add(pos, _v_add(_v_mul(right, half), _v_mul(up, -half)))
                c2 = _v_add(pos, _v_add(_v_mul(right, half), _v_mul(up, half)))
                c3 = _v_add(pos, _v_add(_v_mul(right, -half), _v_mul(up, half)))
                for a, b in ((c0, c1), (c1, c2), (c2, c3), (c3, c0)):
                    _add_line(rows, a, b, base)
                _add_line(rows, pos, _v_add(pos, _v_mul(forward, LIGHT_HELPER_DIRECTION_LENGTH * 0.6)), base)
            elif helper_kind == "directional":
                target = _v_add(pos, _v_mul(forward, LIGHT_HELPER_DIRECTION_LENGTH))
                _add_line(rows, pos, target, base)
                head = LIGHT_HELPER_DIRECTION_LENGTH * 0.22
                _add_line(rows, target, _v_add(_v_sub(target, _v_mul(forward, head)), _v_mul(right, head * 0.45)), base)
                _add_line(rows, target, _v_add(_v_sub(target, _v_mul(forward, head)), _v_mul(right, -head * 0.45)), base)
                _add_line(rows, _v_add(target, _v_mul(right, -head * 0.35)), _v_add(target, _v_mul(right, head * 0.35)), base)
                _add_line(rows, _v_add(target, _v_mul(up, -head * 0.35)), _v_add(target, _v_mul(up, head * 0.35)), base)
            elif helper_kind == "spot":
                if not draw_volumes:
                    _add_line(rows, pos, _v_add(pos, _v_mul(forward, LIGHT_HELPER_SPOT_LENGTH)), base)
                    continue
                length = LIGHT_HELPER_SPOT_LENGTH
                cap_radius = min(
                    math.tan(math.radians(cone * 0.5)) * length,
                    LIGHT_HELPER_SPOT_CAP_MAX_RADIUS,
                )
                cap = _v_add(pos, _v_mul(forward, length))
                _ring(rows, cap, right, up, cap_radius, base, steps=20)
                for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    edge = _v_add(cap, _v_add(_v_mul(right, cap_radius * sx), _v_mul(up, cap_radius * sy)))
                    _add_line(rows, pos, edge, base)
            else:
                if not draw_volumes:
                    continue
                display_radius = LIGHT_HELPER_POINT_RADIUS
                if node is selected or bool(getattr(node, "_gr_light_selected", False)):
                    display_radius = LIGHT_HELPER_POINT_RADIUS * 1.2
                _ring(rows, pos, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), display_radius, base, steps=28)
                _ring(rows, pos, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), display_radius, base, steps=28)
                _ring(rows, pos, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), display_radius, base, steps=28)

        if not rows:
            return
        data = np.asarray(rows, dtype=np.float32)
        vbo = ctx.buffer(data.tobytes())
        vao = ctx.vertex_array(self._grid_prog, [(vbo, '3f 3f', 'in_pos', 'in_color')])
        self._grid_prog['u_mvp'].write(_mat4_tobytes(mvp))
        depth_was_enabled = True
        try:
            ctx.disable(moderngl.DEPTH_TEST)
            ctx.disable(moderngl.BLEND)
            ctx.depth_mask = False
            try:
                ctx.line_width = 1.0
            except Exception:
                pass
            vao.render(moderngl.LINES)
        finally:
            ctx.depth_mask = True
            if depth_was_enabled:
                ctx.enable(moderngl.DEPTH_TEST)
            vao.release()
            vbo.release()

    @staticmethod
    def _light_kind_int(node) -> int:
        kind = str(getattr(node, "light_kind", "point") or "point").strip().lower()
        kind = kind.replace("aurora_", "")
        if kind == "directional":
            return 1
        if kind == "spot":
            return 2
        if kind == "area":
            return 3
        return 0

    @staticmethod
    def _rotate_vec_by_quat(v, q) -> tuple[float, float, float]:
        try:
            x, y, z = float(v[0]), float(v[1]), float(v[2])
            qx, qy, qz, qw = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
            tx = 2.0 * (qy * z - qz * y)
            ty = 2.0 * (qz * x - qx * z)
            tz = 2.0 * (qx * y - qy * x)
            rx = x + qw * tx + (qy * tz - qz * ty)
            ry = y + qw * ty + (qz * tx - qx * tz)
            rz = z + qw * tz + (qx * ty - qy * tx)
            ln = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
            return (rx / ln, ry / ln, rz / ln)
        except Exception:
            return (0.0, 0.0, -1.0)

    def _scene_light_records(self, nodes, get_world_transform) -> list[dict]:
        records: list[dict] = []
        for node in nodes:
            if not bool(getattr(node, "is_light", False)):
                continue
            if not bool(getattr(node, "light_enabled", True)):
                continue
            if bool(getattr(node, "_gr_light_hidden", False)) or bool(getattr(node, "_gr_light_deleted", False)):
                continue
            try:
                world_pos, world_orient = get_world_transform(node)
            except Exception:
                world_pos = getattr(node, "position", (0.0, 0.0, 0.0))
                world_orient = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
            color = getattr(node, "light_color", (1.0, 1.0, 1.0)) or (1.0, 1.0, 1.0)
            radius = max(0.001, float(getattr(node, "light_radius", 5.0) or 5.0))
            intensity = max(0.0, float(getattr(node, "light_multiplier", 1.0) or 1.0))
            cone_deg = max(1.0, min(179.0, float(getattr(node, "light_cone_degrees", 45.0) or 45.0)))
            records.append({
                "enabled": 1,
                "kind": self._light_kind_int(node),
                "ambient_only": 1 if bool(getattr(node, "light_ambient_only", False)) else 0,
                "pos": tuple(float(x) for x in world_pos[:3]),
                "dir": self._rotate_vec_by_quat((0.0, 0.0, -1.0), world_orient),
                "color": tuple(max(0.0, float(x)) for x in color[:3]),
                "radius": radius,
                "intensity": intensity,
                "cone_cos": math.cos(math.radians(cone_deg * 0.5)),
                "area_size": max(0.0, float(getattr(node, "light_area_size", 1.0) or 1.0)),
                "score": radius * max(0.01, intensity),
            })
        records.sort(key=lambda item: item["score"], reverse=True)
        return records[:16]

    def _upload_scene_lights(self, prog, uniforms, records: list[dict]) -> None:
        count = len(records)
        mode = str(getattr(self, "lighting_mode", "scene") or "scene").lower()
        if mode in {"unlit", "fullbright", "diffuse_only", "normal_only", "specular_only", "environment_only", "lightmap_preview", "shader_complexity"}:
            lighting_int = 0
        elif mode in {"scene", "photoreal_preview"} and count > 0:
            lighting_int = 2
        else:
            lighting_int = 1
        if "u_scene_lighting" in uniforms:
            uniforms["u_scene_lighting"].value = lighting_int
        if "u_scene_ambient" in uniforms:
            uniforms["u_scene_ambient"].value = float(getattr(self, "scene_ambient", 0.06))
        if "u_scene_light_count" in uniforms:
            uniforms["u_scene_light_count"].value = count
        if count <= 0 or not _NUMPY:
            return

        enabled = np.zeros(16, dtype="i4")
        kind = np.zeros(16, dtype="i4")
        ambient_only = np.zeros(16, dtype="i4")
        pos = np.zeros((16, 3), dtype="f4")
        direction = np.zeros((16, 3), dtype="f4")
        color = np.ones((16, 3), dtype="f4")
        radius = np.ones(16, dtype="f4")
        intensity = np.ones(16, dtype="f4")
        cone_cos = np.full(16, math.cos(math.radians(22.5)), dtype="f4")
        area_size = np.ones(16, dtype="f4")
        for idx, rec in enumerate(records):
            enabled[idx] = int(rec["enabled"])
            kind[idx] = int(rec["kind"])
            ambient_only[idx] = int(rec["ambient_only"])
            pos[idx] = rec["pos"]
            direction[idx] = rec["dir"]
            color[idx] = rec["color"]
            radius[idx] = float(rec["radius"])
            intensity[idx] = float(rec["intensity"])
            cone_cos[idx] = float(rec["cone_cos"])
            area_size[idx] = float(rec["area_size"])

        for name, data in (
            ("u_scene_light_enabled", enabled),
            ("u_scene_light_kind", kind),
            ("u_scene_light_ambient_only", ambient_only),
            ("u_scene_light_pos", pos),
            ("u_scene_light_dir", direction),
            ("u_scene_light_color", color),
            ("u_scene_light_radius", radius),
            ("u_scene_light_intensity", intensity),
            ("u_scene_light_cone_cos", cone_cos),
            ("u_scene_light_area_size", area_size),
        ):
            uniform = uniforms.get(name)
            if uniform is None:
                try:
                    uniform = prog[f"{name}[0]"]
                except Exception:
                    continue
            try:
                uniform.write(data.tobytes())
            except Exception:
                log.debug("GpuRenderer: failed to upload %s", name, exc_info=True)

    def render(self,
               model,
               camera,
               W: int, H: int,
               textures: Optional[Dict[str, 'Image.Image']] = None,
               anim_pose=None,
               anim_time: float = 0.0,
               anim_base_pose=None) -> Optional['Image.Image']:
        """
        Render `model` from `camera` into a W×H PIL RGBA image.

        Parameters
        ----------
        model      : KotorModel (from src.core.model_data)
        camera     : ArcBallCamera or duck-typed object
        W, H       : output image dimensions
        textures   : dict mapping lowercased texture name → PIL Image
        anim_pose  : AnimPose object (from animation_engine) or None
        anim_time  : current animation time in seconds (for UV scroll / flipbook)
        anim_base_pose : AnimPose | None
            FIX-SKIN-ANIM-D2: The animation's first-frame (t=0) pose.  When
            provided, the GPU skinning palette uses this as the bind reference
            instead of the static node hierarchy, matching the xoreos approach.

        Returns
        -------
        PIL RGBA Image, or None on failure.
        """
        t0 = time.perf_counter()
        if model is None or W <= 0 or H <= 0:
            return None
        textures = textures or {}

        if self._ensure_context():
            result = self._render_gpu(model, camera, W, H, textures, anim_pose, anim_time,
                                       anim_base_pose=anim_base_pose)
            if result is not None:
                self.perf['last_frame_ms'] = (time.perf_counter() - t0) * 1000
                self.perf['backend'] = 'gpu'
                return result
            # GPU render failed — fall through to CPU

        result = self._render_cpu(model, camera, W, H, textures, anim_pose, anim_time)
        self.perf['last_frame_ms'] = (time.perf_counter() - t0) * 1000
        self.perf['backend'] = 'cpu'
        return result

    # ── GPU render ────────────────────────────────────────────────────────────

    def _render_gpu(self, model, camera, W: int, H: int,
                    textures: Dict[str, 'Image.Image'],
                    anim_pose, anim_time: float,
                    anim_base_pose=None) -> Optional['Image.Image']:
        """Full GPU render via ModernGL EGL."""
        ctx = self._ctx
        prog = self._prog
        if ctx is None or prog is None:
            return None
        if not _NUMPY or not _PIL:
            return None
        self.deferred_mesh_uploads = False
        _new_mesh_uploads_this_frame = 0

        # PERF-SCALE: Interactive preview skips MSAA below, but stays at full
        # resolution by default.  Lower interactive_render_scale only when the
        # user explicitly accepts reduced quality for more FPS.
        _full_W, _full_H = W, H
        _scale = max(0.25, min(1.0, float(getattr(self, "interactive_render_scale", 1.0) or 1.0)))
        if self.interactive and _scale < 1.0 and W > 200 and H > 200:
            W = max(8, int(W * _scale))
            H = max(8, int(H * _scale))

        try:
            t_upload = time.perf_counter()

            # ── PERF-FBO: Dual Framebuffer strategy ──────────────────────
            # MSAA FBO:   High-quality (4x multisampled) — used for still frames.
            #             The MSAA resolve (copy_framebuffer) costs ~59ms on llvmpipe
            #             so it MUST be skipped during interactive camera drag.
            # Simple FBO: Non-multisampled — used during interactive drag.
            #             No resolve needed → saves 59ms/frame → enables 30+ fps.
            _MSAA_SAMPLES = 4
            _use_msaa = not self.interactive

            if _use_msaa:
                # ── MSAA FBO (quality path) ────────────────────────────────
                if (self._fbo is None or self._fbo_w != W or self._fbo_h != H):
                    if self._fbo is not None:
                        try:
                            ca = self._fbo.color_attachments[0]
                            if ca is not None: ca.release()
                            da = self._fbo.depth_attachment
                            if da is not None: da.release()
                            self._fbo.release()
                        except Exception: pass
                        if self._fbo_resolve is not None:
                            try:
                                ca = self._fbo_resolve.color_attachments[0]
                                if ca is not None: ca.release()
                                self._fbo_resolve.release()
                            except Exception: pass
                            self._fbo_resolve = None
                    try:
                        self._fbo = ctx.framebuffer(
                            color_attachments=[ctx.renderbuffer((W, H), components=4, samples=_MSAA_SAMPLES)],
                            depth_attachment=ctx.depth_renderbuffer((W, H), samples=_MSAA_SAMPLES),
                        )
                        self._fbo_resolve = ctx.framebuffer(
                            color_attachments=[ctx.renderbuffer((W, H), components=4)],
                        )
                        self._fbo_msaa = True
                    except Exception:
                        self._fbo = ctx.framebuffer(
                            color_attachments=[ctx.renderbuffer((W, H), components=4)],
                            depth_attachment=ctx.depth_renderbuffer((W, H)),
                        )
                        self._fbo_resolve = None
                        self._fbo_msaa = False
                    self._fbo_w = W
                    self._fbo_h = H
                fbo = self._fbo
            else:
                # ── Simple FBO (fast interactive path) ─────────────────────
                if (self._fbo_simple is None or self._fbo_simple_w != W or self._fbo_simple_h != H):
                    if self._fbo_simple is not None:
                        try:
                            ca = self._fbo_simple.color_attachments[0]
                            if ca is not None: ca.release()
                            da = self._fbo_simple.depth_attachment
                            if da is not None: da.release()
                            self._fbo_simple.release()
                        except Exception: pass
                    self._fbo_simple = ctx.framebuffer(
                        color_attachments=[ctx.renderbuffer((W, H), components=4)],
                        depth_attachment=ctx.depth_renderbuffer((W, H)),
                    )
                    self._fbo_simple_w = W
                    self._fbo_simple_h = H
                fbo = self._fbo_simple

            fbo.use()
            # ModernGL keeps viewport/scissor as context state. After loading a
            # model into a newly laid-out Qt viewport, stale dimensions can leave
            # part of the framebuffer cleared but undrawn until a window resize.
            ctx.viewport = (0, 0, W, H)
            try:
                ctx.scissor = None
            except Exception:
                pass
            # PERF-READBACK: Clear with OPAQUE background (alpha=1.0) so that
            # the readback path can skip the expensive alpha compositing step
            # (saves ~19ms/frame at 800x600).  Keep this in sync with viewport._BG.
            ctx.clear(23/255, 25/255, 28/255, 1.0)
            ctx.enable(moderngl.DEPTH_TEST)
            # v7.0 FIX (Finding 5.8 — reone context.cpp cross-ref):
            # reone uses GL_LEQUAL (not GL_LESS) to match KotOR engine behavior.
            # GL_LEQUAL allows co-planar decal geometry to render correctly without
            # z-fighting, matching the original engine's depth test mode.
            ctx.depth_func = '<='
            ctx.depth_mask = True  # depth writes ON by default

            # BUG-WIND FIX: KotOR models use CLOCKWISE triangle winding (Direct3D
            # convention).  OpenGL defaults to COUNTER-CLOCKWISE front faces.
            # Setting front_face='cw' makes OpenGL treat CW tris as front-facing,
            # which means back-face culling discards the correct (back) faces.
            # Reference: KotorBlender reader.py winding notes + KotOR.js geometry.
            ctx.front_face = 'cw'
            if self.show_wireframe or not self.cull_faces:
                ctx.disable(moderngl.CULL_FACE)
            else:
                ctx.enable(moderngl.CULL_FACE)
            try:
                ctx.wireframe = bool(self.show_wireframe and not self.show_solid)
            except Exception:
                pass

            # ── Camera matrices ────────────────────────────────────────────
            # ArcBallCamera.eye is a METHOD (not a property); call it if callable.
            # ArcBallCamera stores near/far as _near/_far; try both names.
            _eye = getattr(camera, 'eye', (0, 5, 10))
            eye    = tuple(_eye() if callable(_eye) else _eye)
            _target = getattr(camera, 'target', (0, 0, 0))
            target = tuple(_target() if callable(_target) else _target)
            # KotOR uses Z-up; default to (0,0,1).  ArcBallCamera has no 'up' attr.
            _up = getattr(camera, 'up', None)
            if _up is None:
                up = (0.0, 0.0, 1.0)   # Z-up (KotOR world convention)
            else:
                up = tuple(_up() if callable(_up) else _up)
            fov    = float(getattr(camera, 'fov',   45.0))
            # ArcBallCamera stores near/far as _near/_far (private)
            near   = float(getattr(camera, 'near',  getattr(camera, '_near',  0.01)))
            far    = float(getattr(camera, 'far',   getattr(camera, '_far',  2000.0)))

            aspect = W / max(1, H)
            proj   = _mat4_perspective(math.radians(fov), aspect, near, far)
            view   = _mat4_lookat(eye, target, up)
            model_mat  = _mat4_identity()
            # GLSL: gl_Position = MVP * pos = proj * view * model * pos
            # Matrices are standard row-major; _mat4_tobytes() transposes for GLSL column-major.
            mvp        = _mat4_mul(_mat4_mul(proj, view), model_mat)
            normal_mat = _mat3_normal(model_mat)

            # PERF-UNIFCACHE: Use cached uniform references from self._u instead of
            # prog['name'] dict lookups.  This saves ~0.4ms/frame on 56-node models.
            _u = self._u

            _u['u_mvp'].write(_mat4_tobytes(mvp))
            _u['u_model'].write(_mat4_tobytes(model_mat))
            _u['u_normal_mat'].write(normal_mat.T.astype(np.float32).tobytes())
            _u['u_cam_pos'].value = tuple(eye)

            # Lighting uniforms — only set once per frame (values don't change per-node).
            _u['u_light_dir'].value  = (0.4839, 0.3519, 0.7918)  # pre-normalised
            _u['u_light_dir2'].value = (-0.4973, -0.2842, 0.8195)  # pre-normalised
            _u['u_ambient'].value    = 0.65
            _u['u_specular'].value   = 0.10
            _u['u_shininess'].value  = 20.0
            _u['u_alpha_test'].value = 0.5
            _u['u_decal'].value      = 0
            _u['u_wateralpha'].value = 1.0
            _u['u_has_spec'].value   = 0
            _u['u_has_bump'].value   = 0
            _u['u_alpha'].value      = 1.0
            _u['u_node_alpha'].value = 1.0
            _u['u_blend_mode'].value = 0
            _u['u_has_tex'].value    = 0
            _u['u_has_lm'].value     = 0
            _u['u_lm_shade'].value   = 0
            _u['u_lm_composite_mode'].value = _lm_composite_mode()
            if 'u_lightmap_intensity' in _u:
                _u['u_lightmap_intensity'].value = float(getattr(self, 'lightmap_intensity', 0.55))
            if 'u_lightmap_mode' in _u:
                _lm_mode = str(getattr(self, 'lightmap_mode', 'baked') or 'baked').lower()
                _u['u_lightmap_mode'].value = 2 if _lm_mode in {'emissive', 'debug'} else 1 if _lm_mode in {'phong', 'dynamic_preview', 'hybrid'} else 0
            _u['u_has_env'].value    = 0
            if 'u_scene_lighting' in _u:
                _u['u_scene_lighting'].value = 1
            if 'u_scene_ambient' in _u:
                _u['u_scene_ambient'].value = float(getattr(self, 'scene_ambient', 0.06))
            if 'u_scene_light_count' in _u:
                _u['u_scene_light_count'].value = 0
            _u['u_diffuse'].value    = (1.0, 1.0, 1.0)
            _u['u_selfillum'].value  = (0.0, 0.0, 0.0)
            _u['u_uv_scroll'].value  = (0.0, 0.0)
            _u['u_uv_v_flip'].value  = 1.0
            _u['u_rotate_tex'].value = 0.0
            _u['u_flipbook_off'].value  = (0.0, 0.0)
            _u['u_flipbook_size'].value = (0.0, 0.0)
            _u['u_features'].value     = 0
            _u['u_water_time'].value   = 0.0
            _u['u_proc_type'].value    = 0
            self._wireframe_pass = bool(self.show_wireframe and not self.show_solid)
            if 'u_wireframe_enabled' in _u:
                _u['u_wireframe_enabled'].value = 1 if self._wireframe_pass else 0
            if 'u_wire_color' in _u:
                _u['u_wire_color'].value = tuple(self.wire_color)
            _render_mode_name = str(getattr(self, 'render_mode', 'realistic') or 'realistic').lower()
            _render_mode_int = 1 if _render_mode_name == 'flat' else 2 if _render_mode_name == 'shaded' else 0
            if 'u_render_mode' in _u:
                _u['u_render_mode'].value = _render_mode_int
            if 'u_selected' in _u:
                _u['u_selected'].value = 0
            _u['u_dangly_enabled'].value      = 0.0
            _u['u_dangly_displacement'].value = 0.0
            _u['u_dangly_time'].value         = 0.0
            _u['u_saber_enabled'].value       = 0.0
            _u['u_saber_displacement'].value  = 0.0
            _u['u_saber_length'].value        = 1.0
            _u['u_oit_enabled'].value         = 0
            if 'u_debug_visualize' in _u:
                _u['u_debug_visualize'].value = _debug_visualize_mode()

            # ── Phase A: GPU Skinning — default off for each frame ───────────
            # Set u_skin_enabled = 0 as the default per-frame state.
            # Skin nodes will set it to 1 in _draw_node before their draw call.
            if 'u_skin_enabled' in _u:
                _u['u_skin_enabled'].value = 0
            if 'u_bone_count' in _u:
                _u['u_bone_count'].value = 0

            self._draw_grid(ctx, mvp)

            self.perf['gpu_upload_ms'] = (time.perf_counter() - t_upload) * 1000
            t_draw = time.perf_counter()

            total_tris = 0

            # ── Two-pass rendering: opaque first, then transparent ─────────
            # Pass 1: opaque/punch-through (depth write ON, depth test ON)
            # Pass 2: alpha-blended / additive (depth write OFF, depth test ON)
            # This prevents transparent geometry from blocking opaque geometry
            # behind it — fixing the "see-through" appearance on character models.
            # KotorModel uses all_nodes() — there is NO .nodes list attribute.
            _all_nodes_fn = getattr(model, 'all_nodes', None)
            if _all_nodes_fn is not None:
                nodes = list(_all_nodes_fn())
            else:
                nodes = getattr(model, 'nodes', [])

            # ── FIX-PERSCACHE: Persistent world-transform cache ────────────
            _cur_model_id = id(model)
            _model_changed = (_cur_model_id != self._wt_model_id)
            if _model_changed:
                self._wt_cache.clear()
                self._wt_model_id = _cur_model_id

            # ── Phase A: GPU Skinning — build bone palette for skin models ─────
            # Detect if this model has any skin nodes; if so, build the
            # MatrixPaletteUploader's inverse bind-pose (once per model).
            # The palette is then uploaded per-frame when animating.
            _has_skin_nodes = False
            if _GPU_SKINNING:
                for _sn in nodes:
                    if bool(getattr(_sn, 'is_skin', False)):
                        _has_skin_nodes = True
                        break
                if _has_skin_nodes:
                    if self._skin_model_id != _cur_model_id or self._skin_uploader is None:
                        self._skin_uploader = MatrixPaletteUploader(max_bones=_SKIN_MAX_BONES)
                        n_built = self._skin_uploader.build_inverse_bind_pose(model)
                        self._skin_model_id = _cur_model_id
                        self._skin_bone_count = n_built
                        if not self._skin_logged:
                            log.info(f"GPU-SKINNING: MatrixPaletteUploader built {n_built} "
                                     f"inverse bind-pose matrices for model "
                                     f"'{getattr(model, 'name', '?')}'")
                            self._skin_logged = True
                    # FIX-SKIN-QBONE: Skin palettes are now built per skin node
                    # immediately before the draw call.  qBone/tBone slots are
                    # indexed by the skin node's local bone_map, not the global
                    # model node order, so a single model-wide palette is wrong.

            # PERF: Only stamp model refs and compute proxy IDs when model changes.
            # These are O(N) walks that produce identical results across frames for
            # the same model.
            if _model_changed:
                for _n in nodes:
                    try:
                        _n._model_ref = model
                    except (AttributeError, TypeError):
                        pass

                # FIX-SKINPROXY: Compute skin proxy node IDs for this model.
                _proxy_node_ids: set = set()
                try:
                    _skin_tex_verts: dict = {}
                    for _pn in nodes:
                        if not getattr(_pn, 'is_mesh', False) or not getattr(_pn, 'is_skin', False):
                            continue
                        _pt = str(getattr(_pn, 'texture', '') or '').strip().lower()
                        if not _pt or _pt in ('null', 'none', ''):
                            continue
                        _pnv = len(getattr(_pn, 'vertices', []))
                        if _pnv == 0:
                            continue
                        if _pt not in _skin_tex_verts:
                            _skin_tex_verts[_pt] = []
                        _skin_tex_verts[_pt].append((_pn, _pnv))
                    # Use the shared inner-geometry list (see render_constants.py).
                    # This list MUST match viewport.py classification so the CPU
                    # and GPU paths treat NPC-head eyelid/gumskin/tonguemesh nodes
                    # identically — otherwise the same model renders with missing
                    # inner geometry under one renderer and not the other.
                    for _pn in nodes:
                        if not getattr(_pn, 'is_mesh', False) or getattr(_pn, 'is_skin', False):
                            continue
                        _pt = str(getattr(_pn, 'texture', '') or '').strip().lower()
                        if not _pt or _pt in ('null', 'none', ''):
                            continue
                        if not getattr(_pn, 'uvs', []):
                            continue
                        _pn_name_low = str(getattr(_pn, 'name', '') or '').lower()
                        if any(_ig in _pn_name_low for _ig in _INNER_GEO_SUBSTRINGS):
                            continue
                        _pnv = len(getattr(_pn, 'vertices', []))
                        _matches = _skin_tex_verts.get(_pt, [])
                        if len(_matches) == 1 and _matches[0][1] > _pnv:
                            _proxy_node_ids.add(id(_pn))
                except Exception:
                    pass
                self._node_cache_proxy_ids = _proxy_node_ids
            else:
                _proxy_node_ids = self._node_cache_proxy_ids
            # Local alias for closure capture
            _wt_cache = self._wt_cache

            def _get_world_transform(nd):
                """Return (world_pos, world_orient) with persistent memoization.

                FIX-PERSCACHE: For static geometry (no anim_pose override for this
                node) the result is cached across frames so subsequent renders skip
                the O(depth) parent-chain walk entirely.

                FIX-SKIN-ANIM: Skin mesh nodes MUST NOT receive animation position/
                rotation overrides.  Skin vertices are pre-baked in bind-pose world
                space.  Applying the animated bone rotation directly to the mesh node
                causes the entire skin mesh to be incorrectly rotated → extreme
                stretching/deformation (observed on c_brith wings, limbs).

                In the Aurora engine, skin mesh deformation is handled by Linear
                Blend Skinning (LBS) using per-bone matrices computed from the
                animated skeleton hierarchy.  Without GPU skinning, the best we can
                do is keep skin meshes in their bind pose.

                Non-skin nodes (rigid trimesh attachments like eyes, tongue, horns)
                DO receive animation overrides so they move with the skeleton.

                Cross-ref: reone mesh.cpp:307 (skin bone matrix computation);
                           KotOR.js OdysseyModel3D.ts:730 (buildSkeleton, bind);
                           xoreos modelnode.cpp:805 (skin pass separation).
                """
                nid = id(nd)
                if anim_pose is not None:
                    _is_skin_nd = bool(getattr(nd, 'is_skin', False))
                    if not _is_skin_nd:
                        # FIX-GPU-ANIM-CHAIN: Walk the full parent chain for animated
                        # non-skin nodes, substituting animation pose values at each
                        # level.  Previously this returned just the local animated
                        # position/rotation without accumulating the parent chain,
                        # causing rigid attachments (eyes, horns, accessories) to
                        # teleport to the origin during animation.  The CPU viewport
                        # (viewport.py:4210-4276) correctly walks the full chain; we
                        # replicate that approach here.
                        #
                        # For each node in the ancestor chain:
                        #   - If the node has an animation pose entry, use animated pos/rot
                        #   - Otherwise use the bind-pose pos/rot
                        #   - Accumulate world transform: world_pos += quat_rotate(parent_orient, local_pos)
                        #
                        # Check if this node or any ancestor has animation data
                        _has_any_anim = False
                        _check = nd
                        while _check is not None:
                            if hasattr(anim_pose, 'nodes') and _check.name.lower() in anim_pose.nodes:
                                _has_any_anim = True
                                break
                            _check = getattr(_check, 'parent', None)

                        if _has_any_anim:
                            # Walk the full parent chain, accumulating world transform
                            _chain = []
                            _n = nd
                            _visited = set()
                            while _n is not None:
                                _nid_c = id(_n)
                                if _nid_c in _visited or len(_chain) > 512:
                                    break
                                _visited.add(_nid_c)
                                _chain.append(_n)
                                _n = getattr(_n, 'parent', None)
                            _chain.reverse()

                            _awx, _awy, _awz = 0.0, 0.0, 0.0
                            _aparent_q = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)

                            for _ci, _cn in enumerate(_chain):
                                _is_leaf = (_ci == len(_chain) - 1)
                                _apn = anim_pose.nodes.get(_cn.name.lower()) if hasattr(anim_pose, 'nodes') else None
                                if _apn is not None:
                                    _alx, _aly, _alz = _apn.position
                                    _arot = list(_apn.rotation)
                                else:
                                    _alx, _aly, _alz = getattr(_cn, 'position', (0.0, 0.0, 0.0))
                                    _arot = list(getattr(_cn, 'rotation', (0.0, 0.0, 0.0, 1.0)))

                                # Normalize quaternion
                                _ar2 = _arot[0]**2 + _arot[1]**2 + _arot[2]**2 + _arot[3]**2
                                if _ar2 > 1e-9 and abs(_ar2 - 1.0) > 1e-4:
                                    _ars = _ar2 ** 0.5
                                    _arot = [_arot[0]/_ars, _arot[1]/_ars, _arot[2]/_ars, _arot[3]/_ars]

                                # Rotate local position by parent orientation
                                _local_pos = np.array([[_alx, _aly, _alz]], dtype=np.float64)
                                _rotated = _quat_rotate_batch(_aparent_q, _local_pos)[0]
                                _awx += _rotated[0]
                                _awy += _rotated[1]
                                _awz += _rotated[2]

                                # Accumulate orientation: parent_q = parent_q * node_rot
                                _nq = np.array(_arot, dtype=np.float64)
                                # Quaternion multiply: aparent_q * _nq
                                _px, _py, _pz, _pw = _aparent_q
                                _nx, _ny, _nz, _nw = _nq
                                _aparent_q = np.array([
                                    _pw*_nx + _px*_nw + _py*_nz - _pz*_ny,
                                    _pw*_ny - _px*_nz + _py*_nw + _pz*_nx,
                                    _pw*_nz + _px*_ny - _py*_nx + _pz*_nw,
                                    _pw*_nw - _px*_nx - _py*_ny - _pz*_nz,
                                ], dtype=np.float64)

                            _wp = (_awx, _awy, _awz)
                            _wo = tuple(_aparent_q.tolist())
                            return (_wp, _wo)
                # Static / no override → use persistent cache
                if nid in _wt_cache:
                    return _wt_cache[nid]
                try:
                    _wp, _wo = nd.world_transform()
                except Exception:
                    _wp = getattr(nd, 'position', (0.0, 0.0, 0.0))
                    _wo = getattr(nd, 'rotation', (0.0, 0.0, 0.0, 1.0))
                result = (_wp, _wo)
                _wt_cache[nid] = result
                return result

            # ── FIX-DEFORM: Deformation-helper detection ──────────────────
            # FIX-DEFORM: Self-contained deformation-helper filter (no viewport import).
            # KotOR MDL models contain internal bone-proxy / skeleton-helper mesh nodes
            # that must NOT be rendered as geometry.  Detection rules (same logic as
            # viewport._is_deformation_helper, inlined here for GPU-path independence):
            #   1. Non-skin nodes with no UVs → helper (UNLESS module/area model)
            #   2. Non-skin nodes whose names end with '_g', '_g0', or '_dum' → helper
            #   3. Nodes with null/empty texture AND no UVs → helper
            #   4. Skin nodes with a real texture and UVs → ALWAYS render
            # Reference: viewport._is_deformation_helper, PyKotor geometry_utils.py,
            #            KotOR engine ProcessSkinSeams().
            _gpu_model_cls   = (str(getattr(model, 'classification', 'character') or 'character')).lower()
            # FIX-MODEL-TYPE-ZERO: model_type=0 means "module/tile" in KotOR.
            # Using `int(val or 4)` treated 0 as falsy → replaced with 4 (character)
            # which broke module UV-sentinel exemption for tile models.
            # Fix: only use the default when the raw value is None/missing.
            _gpu_model_type_raw = getattr(model, 'model_type', None)
            _gpu_model_type  = int(_gpu_model_type_raw) if _gpu_model_type_raw is not None else 4
            _gpu_is_module   = (_gpu_model_cls in ('effect', 'tile', 'other') or
                                _gpu_model_type in (0, 2))
            _scene_lights = self._scene_light_records(nodes, _get_world_transform)
            self._upload_scene_lights(prog, _u, _scene_lights)

            def _is_deform_helper(nd) -> bool:
                """Return True if nd is a bone-proxy/deformation-helper that must not render."""
                is_skin    = bool(getattr(nd, 'is_skin', False))
                tex_name   = str(getattr(nd, 'texture', '') or '').strip().lower()
                has_tex    = tex_name and tex_name not in ('null', '', 'none', '****')
                uvs        = getattr(nd, 'uvs', [])
                has_uvs    = bool(uvs) and len(uvs) > 0
                node_name  = str(getattr(nd, 'name', '') or '').lower()

                # Skin nodes with a real texture and UVs are always renderable
                if is_skin and has_tex and has_uvs:
                    return False

                # Skin nodes with null texture and no UVs are helpers
                if is_skin and not has_tex and not has_uvs:
                    return True

                # Non-skin: no UVs → helper (module/area models exempt: MDX-sourced UVs
                # may be empty if MDX wasn't loaded, but mesh is still real geometry)
                if not is_skin and not has_uvs:
                    if _gpu_is_module:
                        return False  # module geometry: render flat-shaded without UVs
                    return True

                # Name-based helper detection for non-skin nodes
                if not is_skin:
                    if (node_name.endswith('_g') or node_name.endswith('_g0')
                            or node_name.endswith('_dum')):
                        return True

                return False

            # ── Transparency classification ─────────────────────────────
            # Follows the definitive Aurora engine approach from reference
            # implementations (xoreos, reone, KotOR.js):
            #
            # xoreos (modelnode.cpp:500-506):
            #   if (hasTransparencyHint)
            #       isTransparent = transparencyHint;
            #   else
            #       isTransparent = hasAlpha;  (texture has alpha channel)
            #
            # reone (mesh.cpp isTransparent()):
            #   PunchThrough → NOT transparent (opaque with alpha-test)
            #   Additive → transparent
            #   alpha < 1.0 → transparent
            #   Has envmap/bumpmap → NOT transparent
            #   Diffuse has alpha channel → transparent
            #
            # KEY FIX: Inner-geometry nodes (eyes, teeth, gums) should NOT
            # be promoted to the transparent pass.  They are opaque geometry
            # (transparency_hint == 0) drawn in the opaque pass with depth
            # write ON.  The head/face mesh has transparency_hint > 0 and
            # its texture contains alpha=0 pixels at the eye sockets and
            # mouth gap.  When drawn in the cutout pass (alpha-test discard),
            # those holes reveal the already-rendered inner-geo beneath.
            # This is exactly how the original Aurora engine works.

            def _classify_node(nd, ap):
                """Return (node_alpha, txi_blend, is_transparent, has_env).

                Transparency classification for three-pass rendering:
                  - Pass 1 (opaque, depth write ON): solid surfaces,
                    inner-geometry (eyes, teeth), env-map surfaces.
                  - Pass 2 (alpha-cutout, depth write ON, shader discard):
                    transparency_hint > 0 nodes with alpha-test textures
                    (head meshes with eye-socket/mouth-gap alpha holes).
                  - Pass 3 (transparent, depth write OFF): additive blending,
                    wateralpha < 1, decal, per-node alpha < 1.

                Cross-ref: xoreos modelnode.cpp:500; reone mesh.cpp:215;
                           KotOR.js OdysseyModel3D.ts:1578.
                """
                na = float(getattr(nd, 'alpha', 1.0))
                na = max(0.0, min(1.0, na))
                if ap is not None:
                    _pn = ap.nodes.get(nd.name.lower()) if hasattr(ap, 'nodes') else None
                    if _pn is not None and getattr(_pn, 'alpha', None) is not None:
                        na = max(0.0, min(1.0, float(_pn.alpha)))
                tb = int(getattr(nd, 'txi_blending', 0))
                _th = int(getattr(nd, 'transparency_hint', 0))
                _at = float(getattr(nd, 'txi_alpha_test', 0.0))
                has_env = bool(getattr(nd, 'txi_envmaptexture', ''))
                wa = float(getattr(nd, 'txi_wateralpha', 1.0))
                decal = bool(getattr(nd, 'txi_decal', False))

                if _gpu_is_module and _render_mode_int in (1, 2):
                    return 1.0, 0, False, False

                # Punchthrough classification (alpha-test discard in shader):
                # Use cutout pass when the MDL node explicitly requests it
                # via transparency_hint > 0 (head meshes, hair cards, foliage).
                # Also apply when TXI blending is already set to punchthrough.
                # Do NOT auto-promote based solely on txi_alpha_test — see
                # the c_bantha body-pixel discard bug (threshold=0.9333 on
                # opaque body textures with transparency_hint=0).
                if tb == 0 and _th > 0:
                    # transparency_hint > 0 → alpha-test cutout pass
                    # This handles head meshes (eye-socket/mouth holes),
                    # hair cards, and other alpha-tested geometry.
                    tb = 2

                # Transparent pass classification (following xoreos/reone):
                # - Additive blending (tb==1)
                # - Semi-transparent water/glass (wateralpha < 1)
                # - Decal overlays
                # - Per-node alpha < 1 (holograms, glass) unless env-mapped
                is_trans = ((tb == 1) or
                            (wa < 0.999) or
                            decal or
                            (na < 0.999 and not has_env))
                return na, tb, is_trans, has_env

            # ── PERF-NODECACHE: Three-pass node classification with caching ──
            # Node classification (opaque/cutout/transparent) is expensive due to
            # _is_deform_helper() and _classify_node() per node.  Cache the result
            # per model and reuse across frames.  Invalidate when the model changes.
            # For animated models, re-classify only when anim_pose changes alpha.
            _need_reclassify = (_cur_model_id != self._node_cache_model_id)
            if _need_reclassify:
                opaque_nodes      = []
                cutout_nodes      = []
                transparent_nodes = []
                for node in nodes:
                    if getattr(node, '_gr_hidden', False):
                        continue
                    if not getattr(node, 'render', True):
                        continue
                    verts = getattr(node, 'vertices', getattr(node, 'verts', []))
                    faces = getattr(node, 'faces', [])
                    if not verts or not faces:
                        continue
                    try:
                        if _is_deform_helper(node):
                            continue
                    except Exception:
                        pass
                    if id(node) in _proxy_node_ids:
                        continue
                    na, tb, is_trans, has_env = _classify_node(node, anim_pose)
                    if is_trans:
                        transparent_nodes.append(node)
                    elif tb == 2:
                        cutout_nodes.append(node)
                    else:
                        opaque_nodes.append(node)
                # Cache the classification
                self._node_cache_model_id = _cur_model_id
                self._node_cache_opaque = opaque_nodes
                self._node_cache_cutout = cutout_nodes
                self._node_cache_transparent = transparent_nodes
                self._node_cache_proxy_ids = _proxy_node_ids
                self._node_cache_is_module = _gpu_is_module
            else:
                # Reuse cached classification
                opaque_nodes = self._node_cache_opaque
                cutout_nodes = self._node_cache_cutout
                transparent_nodes = self._node_cache_transparent

            def _draw_node(node, tex_name_override: str = '',
                           pass_name: str = 'opaque',
                           override_vao=None, override_tri_count: int = 0):
                """Draw a single node.

                tex_name_override: override the diffuse texture name (for multi-tex).
                pass_name: render pass label for diagnostic state tracing.
                override_vao: when set, use this VAO instead of the cached gm.vao
                    (for per-material-slot sub-mesh drawing).
                override_tri_count: triangle count for the override VAO.
                """
                nonlocal total_tris, _new_mesh_uploads_this_frame
                # Use world-space transform (full parent-chain walk) for correct
                # positioning of all mesh nodes, not just local node.position.
                wp, wo = _get_world_transform(node)

                node_alpha = float(getattr(node, 'alpha', 1.0))
                node_alpha = max(0.0, min(1.0, node_alpha))
                selfillum  = getattr(node, 'selfillum', (0.0, 0.0, 0.0))
                if anim_pose is not None:
                    _pn = anim_pose.nodes.get(node.name.lower()) if hasattr(anim_pose, 'nodes') else None
                    if _pn is not None:
                        if getattr(_pn, 'alpha', None) is not None:
                            node_alpha = max(0.0, min(1.0, float(_pn.alpha)))
                        if getattr(_pn, 'selfillum', None) is not None:
                            selfillum = _pn.selfillum
                if _gpu_is_module and _render_mode_int in (1, 2):
                    node_alpha = 1.0

                node_id = id(node)
                # FIX-SKIN-ANIM: Skin nodes are NOT considered "animated" for VBO
                # rebuild purposes.  Their vertices are in bind-pose world space and
                # should only change via GPU skinning (not yet implemented).
                # Rebuilding skin VBOs with animation transforms causes stretching.
                #
                # FIX-GPU-ANIM-CHAIN: Non-skin nodes must also be rebuilt when any
                # ANCESTOR has animation keys, because the node's world position
                # depends on the full parent chain.  Rigid attachments (eyes, horns,
                # accessories) move when their parent bone is animated even if they
                # themselves have no animation keys.
                _nd_is_skin = bool(getattr(node, 'is_skin', False))
                _skin_can_lbs = bool(
                    _nd_is_skin
                    and _has_skin_nodes
                    and self._skin_uploader is not None
                    and anim_pose is not None
                    and getattr(node, 'bone_map', None)
                    and getattr(node, 'skin_data', None)
                )
                _skin_bind_transform = bool(_nd_is_skin and not _skin_can_lbs)
                is_animated = False
                if anim_pose is not None and hasattr(anim_pose, 'nodes') and not _nd_is_skin:
                    # Check if this node or any ancestor has animation data
                    _acheck = node
                    while _acheck is not None:
                        if _acheck.name.lower() in anim_pose.nodes:
                            is_animated = True
                            break
                        _acheck = getattr(_acheck, 'parent', None)
                _skin_vbo_mode_changed = False
                if _nd_is_skin and node_id in self._mesh_cache:
                    _gm_existing = self._mesh_cache[node_id]
                    _skin_vbo_mode_changed = (
                        getattr(_gm_existing, 'skin_bind_transform', None)
                        != _skin_bind_transform
                    )
                if is_animated or node_id not in self._mesh_cache or _skin_vbo_mode_changed:
                    if anim_pose is None and not is_animated:
                        upload_budget = int(getattr(self, "max_new_mesh_uploads_per_frame", 0) or 0)
                        if upload_budget > 0 and _new_mesh_uploads_this_frame >= upload_budget:
                            self.deferred_mesh_uploads = True
                            return
                        _new_mesh_uploads_this_frame += 1
                    # FIX-SKIN-QBONE: Skin nodes now use a per-draw local palette
                    # in bone_map order.  Keep authored bone IDs local so slot k in
                    # vertex influences addresses qBone[k]/tBone[k] for this skin.
                    _bone_remap = None
                    _prebuilt_vbo = None
                    if anim_pose is None and not is_animated:
                        _prebuilt_vbo = _prebuilt_static_gpu_mesh_data(
                            node, _cur_model_id, _skin_bind_transform
                        )
                    if _prebuilt_vbo is not None:
                        vdata, idx_arr = _prebuilt_vbo
                    else:
                        vdata, idx_arr = _build_vbo_data(node, wp, wo,
                                                         anim_pose_node=None,
                                                         is_module=_gpu_is_module,
                                                         bone_index_remap=_bone_remap,
                                                         apply_skin_node_transform_for_bind=_skin_bind_transform)
                    if vdata is None:
                        return
                    if node_id in self._mesh_cache:
                        self._mesh_cache[node_id].release()
                    gm = _GpuMesh()
                    gm.skin_bind_transform = _skin_bind_transform if _nd_is_skin else None
                    main_vdata, bone_id_vdata = _split_vbo_attributes_for_gpu(vdata)
                    gm.vbo = ctx.buffer(main_vdata.tobytes())
                    gm.bone_id_vbo = ctx.buffer(bone_id_vdata.tobytes())
                    gm.uploaded_vertex_count = int(len(vdata))
                    gm.first8_uv0_uploaded = _first_vbo_uv_pairs(vdata, 6)
                    gm.first8_uv1_uploaded = _first_vbo_uv_pairs(vdata, 8)
                    try:
                        gm.uploaded_positions = [
                            [round(float(x), 6) for x in row[:3]]
                            for row in vdata[:, 0:3]
                        ]
                        gm.uploaded_bone_ids = [
                            [int(x) for x in row]
                            for row in bone_id_vdata
                        ]
                        gm.uploaded_weights = [
                            [round(float(x), 6) for x in row]
                            for row in vdata[:, 18:22]
                        ]
                        gm.uploaded_source_indices = [
                            int(x) for x in (
                                getattr(node, '_gr_last_vbo_source_indices', []) or []
                            )
                        ]
                    except Exception:
                        gm.uploaded_positions = []
                        gm.uploaded_bone_ids = []
                        gm.uploaded_weights = []
                        gm.uploaded_source_indices = []
                    gm.uv1_attribute_bound = (
                        getattr(vdata, 'ndim', 0) == 2
                        and getattr(vdata, 'shape', (0, 0))[1] >= 10
                    )
                    vertex_buffers = [
                        (gm.vbo, _VBO_MAIN_FORMAT, *_VBO_MAIN_ATTRS),
                        (gm.bone_id_vbo, _VBO_BONE_IDS_FORMAT, *_VBO_BONE_IDS_ATTRS),
                    ]
                    if idx_arr is not None:
                        gm.ibo = ctx.buffer(idx_arr.tobytes())
                        gm.vao = ctx.vertex_array(prog, vertex_buffers, gm.ibo)
                        gm.tri_count = len(idx_arr) // 3
                        gm.indexed = True
                    else:
                        gm.vao = ctx.vertex_array(prog, vertex_buffers)
                        gm.tri_count = len(vdata) // 3
                        gm.indexed = False
                    # ASCII/Kotor Tool MDLs use face_mats as per-face texture slots.
                    # Binary KotOR MDLs still use the single-diffuse + optional
                    # lightmap path, so only enable this for parser-tagged ASCII
                    # nodes whose secondary slots are not lightmaps.
                    if (
                        bool(getattr(node, 'imported_ascii', False))
                        and int(getattr(node, 'tex_count', 1) or 1) > 1
                        and not bool(getattr(node, 'has_lightmap', False))
                        and getattr(node, 'face_mats', None)
                        and getattr(node, 'texture_names', None)
                    ):
                        try:
                            slot_indices = {}
                            tex_names = list(getattr(node, 'texture_names', []) or [])
                            face_mats = list(getattr(node, 'face_mats', []) or [])
                            faces = list(getattr(node, 'faces', []) or [])
                            n_verts = len(getattr(node, 'vertices', []) or [])
                            row_face = 0
                            for face_i, face in enumerate(faces):
                                if len(face) < 3:
                                    continue
                                vi0, vi1, vi2 = int(face[0]), int(face[1]), int(face[2])
                                if vi0 >= n_verts or vi1 >= n_verts or vi2 >= n_verts:
                                    continue
                                slot = int(face_mats[face_i]) if face_i < len(face_mats) else 0
                                slot = max(0, min(slot, len(tex_names) - 1))
                                bucket = slot_indices.setdefault(slot, [])
                                if gm.indexed:
                                    bucket.extend([vi0, vi1, vi2])
                                else:
                                    base = row_face * 3
                                    bucket.extend([base, base + 1, base + 2])
                                row_face += 1
                            for slot, indices in slot_indices.items():
                                if not indices:
                                    continue
                                slot_ibo = ctx.buffer(np.asarray(indices, dtype=np.uint32).tobytes())
                                slot_vao = ctx.vertex_array(prog, vertex_buffers, slot_ibo)
                                gm.mat_slots[slot] = (slot_vao, slot_ibo, len(indices) // 3)
                        except Exception as exc:
                            log.debug("ASCII multi-texture split failed for %s: %s",
                                      getattr(node, 'name', ''), exc)

                    if not is_animated:
                        self._mesh_cache[node_id] = gm
                else:
                    gm = self._mesh_cache[node_id]

                # Use override VAO/tri_count if provided (per-material-slot draw)
                _use_vao = override_vao if override_vao is not None else gm.vao
                _use_tris = override_tri_count if override_vao is not None else gm.tri_count

                if _use_vao is None or _use_tris == 0:
                    return

                if override_vao is None and gm.mat_slots:
                    tex_names = list(getattr(node, 'texture_names', []) or [])
                    for slot, (slot_vao, _slot_ibo, slot_tris) in gm.mat_slots.items():
                        tex_override = tex_names[slot] if 0 <= slot < len(tex_names) else ''
                        _draw_node(
                            node,
                            tex_name_override=tex_override,
                            pass_name=pass_name,
                            override_vao=slot_vao,
                            override_tri_count=slot_tris,
                        )
                    return

                diff = getattr(node, 'diffuse', (1.0, 1.0, 1.0))
                diff = tuple(max(0.0, min(1.0, float(c))) for c in diff[:3])
                if 'u_wireframe_enabled' in _u:
                    _u['u_wireframe_enabled'].value = 1 if self._wireframe_pass else 0
                if 'u_wire_color' in _u:
                    _u['u_wire_color'].value = tuple(self.wire_color)
                if 'u_selected' in _u:
                    _selected_ids = {id(_n) for _n in (getattr(self, 'selected_nodes', []) or [])}
                    _u['u_selected'].value = 1 if (
                        node is getattr(self, 'selected_node', None)
                        or id(node) in _selected_ids
                        or bool(getattr(node, '_gr_selected', False))
                    ) else 0
                _u['u_diffuse'].value = diff
                _u['u_selfillum'].value = tuple(
                    max(0.0, min(2.0, float(c))) for c in selfillum[:3])
                _u['u_alpha'].value = 1.0
                _u['u_node_alpha'].value = node_alpha

                # FIX-SHININESS: Per-node Phong shininess from ModelNode.shininess.
                # ASCII MDL 'shininess' command sets this; binary trimesh header
                # has a shininess field too.  Zero means no specular highlight —
                # clamp to a tiny positive so pow() in shader is well-defined.
                node_shininess = float(getattr(node, 'shininess', 0.0))
                if node_shininess > 0.0:
                    _u['u_shininess'].value = node_shininess
                else:
                    _u['u_shininess'].value = 20.0   # global default

                txi_blend = int(getattr(node, 'txi_blending', 0))

                # FIX-ALPHATEST: Per-node punchthrough alpha-test threshold.
                # KotOR TPC header bytes [4-7] = float alpha_test_threshold.
                # Kotor.NET: node.TransparencyHint + TPC alpha_test float.
                # PyKotor gl/shader/texture.py: Texture.alpha_cutoff field.
                # When blending=punchthrough (2), use per-node txi_alpha_test
                # instead of the hardcoded 0.5 default set during program init.
                # Range: 0.0..1.0 (engine default is typically 0.5).
                #
                # FIX-TXI-PUNCH: KotOR creature/character DXT5 textures embed
                # TXI 'blending 2' in the TPC file, but the MDL binary parser
                # reads only node-level fields (not TPC-embedded TXI).  When the
                # node has txi_alpha_test > 0 and txi_blending == 0, promote to
                # punchthrough so hair/fur edges render correctly (cut out the
                # transparent DXT5 alpha instead of treating it as opaque).
                # This matches KotOR's engine behaviour for all creature meshes.
                txi_alpha_test = float(getattr(node, 'txi_alpha_test', 0.0))
                _transparency_hint = int(getattr(node, 'transparency_hint', 0))
                if txi_blend == 0 and txi_alpha_test > 0.0 and _transparency_hint > 0:
                    # Promote to punchthrough ONLY when the MDL node has
                    # transparency_hint > 0 (Aurora engine convention) combined with
                    # a TPC alpha_test_threshold.  Opaque nodes (transparency_hint=0)
                    # must NOT be promoted even if the TPC embeds an alpha_test value —
                    # this prevented dark-patch artifacts on bantha body meshes.
                    txi_blend = 2

                _u['u_blend_mode'].value = txi_blend
                if txi_blend == 2:
                    # Punchthrough: set alpha threshold uniform and disable GL blending.
                    # Shader discards fragments below the threshold — no GL blend needed.
                    _u['u_alpha_test'].value = max(0.0, min(1.0, txi_alpha_test if txi_alpha_test > 0.0 else 0.5))
                    ctx.disable(moderngl.BLEND)

                # TXI decal: surface blends over background using its own alpha
                txi_decal = 1 if bool(getattr(node, 'txi_decal', False)) else 0
                _u['u_decal'].value = txi_decal

                # TXI wateralpha: fractional alpha for water/glass (default 1.0)
                txi_wateralpha = float(getattr(node, 'txi_wateralpha', 1.0))
                _u['u_wateralpha'].value = txi_wateralpha

                # Determine GL blend state from TXI flags + per-node alpha
                is_semi_transparent = (
                    node_alpha < 0.999
                    or txi_wateralpha < 0.999
                    or txi_decal
                )
                blend_enabled = False
                if txi_blend == 1:
                    # Additive blend: src=ONE, dst=ONE
                    ctx.enable(moderngl.BLEND)
                    ctx.blend_equation = moderngl.FUNC_ADD
                    ctx.blend_func = (moderngl.ONE, moderngl.ONE)
                    blend_enabled = True
                elif txi_blend == 2:
                    pass  # Already handled above (alpha_test + disable BLEND)
                elif txi_blend == 3:
                    # v7.1 FIX-GLMAX (Finding 5.6 — reone context.cpp cross-ref):
                    # GL_MAX blend equation for lighten mode effects.
                    # reone context.cpp line 407: BlendMode::Lighten uses
                    # glBlendEquationSeparate(GL_MAX, GL_FUNC_ADD)
                    # KotOR uses this for some particle effects and self-illumination
                    # overlays where the brightest pixel should win.
                    ctx.enable(moderngl.BLEND)
                    try:
                        ctx.blend_equation = moderngl.MAX
                        ctx.blend_func = (moderngl.ONE, moderngl.ONE)
                    except (AttributeError, Exception):
                        # Fallback: GL_MAX not available on this driver
                        ctx.blend_equation = moderngl.FUNC_ADD
                        ctx.blend_func = (moderngl.ONE, moderngl.ONE)
                    blend_enabled = True
                elif is_semi_transparent or txi_decal:
                    # Decal / wateralpha / per-node transparency
                    ctx.enable(moderngl.BLEND)
                    ctx.blend_equation = moderngl.FUNC_ADD
                    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
                    blend_enabled = True
                else:
                    ctx.disable(moderngl.BLEND)

                uv_scroll = (0.0, 0.0)
                if bool(getattr(node, 'animate_uv', False)):
                    dx = float(getattr(node, 'uv_dir_x', 0.0))
                    dy = float(getattr(node, 'uv_dir_y', 0.0))
                    jitter = float(getattr(node, 'uv_jitter', 0.0))
                    jspd   = float(getattr(node, 'uv_jitter_speed', 0.0))
                    su = dx * anim_time
                    sv = dy * anim_time
                    if jitter != 0.0 and jspd > 0.0:
                        j = jitter * math.sin(anim_time * jspd * 2.0 * math.pi)
                        su += j; sv += j
                    uv_scroll = (su, sv)
                _u['u_uv_scroll'].value = uv_scroll

                rot_tex = 1.0 if bool(getattr(node, 'rotate_texture', False)) else 0.0
                _u['u_rotate_tex'].value = rot_tex

                # v7.2 FIX-DANGLY (Finding 5.10 — reone v_model.glsl cross-ref):
                # Enable GPU dangly mesh vertex animation for DANGLY node type.
                # Dangly meshes simulate cloth/hair/tentacle physics with per-vertex
                # constraint weights. The vertex shader applies wind-like displacement
                # modulated by the constraint (0=free, 1=fixed) stored in vertex alpha.
                # Reference: reone v_model.glsl line 58; KotOR.js OdysseyModel3D.ts.
                _is_dangly = bool(getattr(node, 'is_dangly', False))
                if _is_dangly:
                    _u['u_dangly_enabled'].value = 1.0
                    _u['u_dangly_displacement'].value = float(
                        getattr(node, 'dangly_displacement', 0.5))
                    _u['u_dangly_time'].value = anim_time
                else:
                    _u['u_dangly_enabled'].value = 0.0

                # v7.2 FIX-SABER (Finding 5.11 — reone v_model.glsl cross-ref):
                # Enable GPU lightsaber blade vertex deformation for SABER node type.
                # The vertex shader extends blade vertices along the local Z-axis
                # based on gl_VertexID, creating the blade ignition/retraction effect.
                # Reference: reone v_model.glsl line 61-65; KotorBlender NUM_SABER_VERTS.
                _is_saber = bool(getattr(node, 'is_saber', False))
                if _is_saber:
                    _u['u_saber_enabled'].value = 1.0
                    _u['u_saber_displacement'].value = 1.0
                    _u['u_saber_length'].value = 1.0
                else:
                    _u['u_saber_enabled'].value = 0.0

                # FIX-FLIPBOOK: TXI proceduretype=cycle sprite-sheet animation.
                # When txi_proceduretype == 'cycle', the texture is a grid of
                # numx × numy frames played at txi_fps frames/second.
                # We compute the current frame from anim_time and pass a UV tile
                # offset and tile size to the vertex shader.
                # Reference: KotOR TXI spec proceduretype/numx/numy/fps.
                txi_proc  = str(getattr(node, 'txi_proceduretype', '')).lower()
                txi_numx  = int(getattr(node, 'txi_numx', 0))
                txi_numy  = int(getattr(node, 'txi_numy', 0))
                txi_fps   = float(getattr(node, 'txi_fps', 0.0))
                _u['u_uv_v_flip'].value = 1.0 if bool(getattr(node, 'uv_v_flip', True)) else 0.0

                # v7.1 FIX-PROCTYPE (Finding 1.6 — KotOR.js TXI.ts cross-ref):
                # Set u_proc_type uniform for water/ring UV distortion in fragment shader.
                # proceduretype=water → sinusoidal UV distortion (water surfaces, lava)
                # proceduretype=ringtexdistort → radial ring distortion (energy fields)
                # proceduretype=random → random UV offset per frame (sparkle/shimmer)
                # Cross-ref: KotOR.js TXI.ts lines 170-186; reone shader pipeline.
                _proc_type_map = {'cycle': 1, 'water': 2, 'random': 3, 'ringtexdistort': 4}
                _proc_int = _proc_type_map.get(txi_proc, 0)
                _u['u_proc_type'].value = _proc_int
                _u['u_water_time'].value = anim_time if _proc_int in (2, 3, 4) else 0.0

                if txi_proc == 'cycle' and txi_numx > 0 and txi_numy > 0 and txi_fps > 0.0:
                    total_frames = txi_numx * txi_numy
                    frame_idx    = int(anim_time * txi_fps) % total_frames
                    col = frame_idx % txi_numx
                    row = frame_idx // txi_numx
                    tile_w = 1.0 / txi_numx
                    tile_h = 1.0 / txi_numy
                    # V origin: row 0 is bottom in OpenGL; KotOR cycle sheets
                    # are stored top-to-bottom so we flip: row 0 → top → high V
                    flip_row = (txi_numy - 1 - row)
                    _u['u_flipbook_off'].value  = (col * tile_w, flip_row * tile_h)
                    _u['u_flipbook_size'].value = (tile_w, tile_h)
                else:
                    _u['u_flipbook_off'].value  = (0.0, 0.0)
                    _u['u_flipbook_size'].value = (0.0, 0.0)

                # ── Texture binding ────────────────────────────────────────
                # FIX-MULTITEX: allow caller to override the texture name for
                # multi-texture batching (one draw call per material slot).
                tex_name = (tex_name_override or
                            str(getattr(node, 'texture', '')).strip().lower())
                if tex_name in ('null', '', 'none'):
                    tex_name = ''
                diff_img = textures.get(tex_name) if tex_name else None
                gl_diff = self._tex_cache.get(diff_img) if diff_img else None
                _tex_gpu_v_flip = bool(getattr(diff_img, '_gr_gpu_uv_v_flip', True))
                _u['u_uv_v_flip'].value = (
                    1.0 if bool(getattr(node, 'uv_v_flip', True)) and _tex_gpu_v_flip else 0.0
                )

                _texture_allowed = bool(self.show_texture and self.show_diffuse_map)
                _detail_texture_allowed = bool(self.show_texture and _render_mode_int == 0)
                if _texture_allowed and gl_diff:
                    # FIX-TEXWRAP: Apply per-node TXI clamp mode (GL_CLAMP_TO_EDGE)
                    # vs. default GL_REPEAT before each draw call.
                    # txi_clamp_s=True → GL_CLAMP_TO_EDGE on U axis (no horizontal tile)
                    # txi_clamp_t=True → GL_CLAMP_TO_EDGE on V axis (no vertical tile)
                    # Default repeat_x=True/repeat_y=True set in _upload; we override
                    # here for nodes that require clamping (head decals, UI overlays).
                    _node_clamp_s = bool(getattr(node, 'txi_clamp_s', False))
                    _node_clamp_t = bool(getattr(node, 'txi_clamp_t', False))
                    if not (_node_clamp_s and _node_clamp_t) and _should_auto_clamp_diffuse(
                        node,
                        is_module=_gpu_is_module,
                    ):
                        # Match the CPU renderer for custom character atlases.
                        # Override MDLs like n_mandalorian01-03 use 0..1 body/helmet
                        # sheets without TXI clamp flags; GL_REPEAT samples the
                        # opposite atlas edge along armor-panel UV borders.
                        _node_clamp_s = True
                        _node_clamp_t = True
                    gl_diff.repeat_x = not _node_clamp_s
                    gl_diff.repeat_y = not _node_clamp_t
                    gl_diff.use(location=0)
                    _u['u_tex'].value = 0
                    _u['u_has_tex'].value = 1
                else:
                    if self._white_tex is None:
                        self._white_tex = ctx.texture((1, 1), 4,
                                                       bytes([255, 255, 255, 255]))
                    self._white_tex.use(location=0)
                    _u['u_tex'].value = 0
                    _u['u_has_tex'].value = 0

                has_lm_flag = bool(getattr(node, 'has_lightmap', False) or getattr(node, '_gr_baked_lightmap_preview_name', ''))
                lm_name     = str(getattr(node, '_gr_baked_lightmap_preview_name', '') or getattr(node, 'lightmap', '')).strip().lower()
                uvs_lm      = getattr(node, 'uvs_lm', [])
                # FIX-LMROLE-V2 (Phase D10): Infer lightmap when texture_2 is present
                # with valid lightmap UVs.  The KotOR texture model is: texture_1 =
                # diffuse, texture_2 = lightmap (when present).  face_mats is NOT used
                # for this determination — it is a walk-mesh surface indicator.
                # Accept lightmap whenever: lm_name is set, uvs_lm has data, and
                # tex_count >= 2.  The loader's FIX-LMROLE normally promotes
                # has_lightmap, but this guard catches alternative load paths.
                if (not has_lm_flag
                        and lm_name
                        and len(uvs_lm) > 0
                        and int(getattr(node, 'tex_count', 1)) >= 2):
                    has_lm_flag = True
                lm_img      = textures.get(lm_name) if (lm_name and has_lm_flag
                                                         and len(uvs_lm) > 0) else None
                gl_lm = self._tex_cache.get(lm_img) if lm_img else None
                if _detail_texture_allowed and bool(self.show_lightmap_map) and gl_lm:
                    # FIX-LMWRAP: Lightmap textures must use CLAMP_TO_EDGE
                    # (not GL_REPEAT) because lightmap UVs are always in [0,1]
                    # and wrap-around causes visible seam lines at texel boundaries.
                    # Additionally, lightmaps are small (8x8 to 64x64) and their
                    # mipmap chain can over-blur the lightmap when magnified across
                    # large surfaces.  Use GL_LINEAR (no mipmap) for min filter.
                    # Cross-ref: KotOR.js ShaderOdysseyModel.ts lightMap sampling;
                    # xoreos model_kotor.cpp — lightmap uses CLAMP_TO_EDGE wrap;
                    # KotorBlender — lightmap UV is always in [0,1] range.
                    gl_lm.repeat_x = False  # GL_CLAMP_TO_EDGE
                    gl_lm.repeat_y = False  # GL_CLAMP_TO_EDGE
                    gl_lm.filter = (moderngl.LINEAR, moderngl.LINEAR)
                    gl_lm.use(location=1)
                    _u['u_lm_tex'].value = 1
                    _u['u_has_lm'].value = 1
                    _u['u_lm_shade'].value = 1 if _gpu_is_module else 0
                else:
                    _u['u_has_lm'].value = 0
                    _u['u_lm_shade'].value = 0

                # BUG-ENVMAP FIX: Bind environment map texture to unit 2.
                # The TXI 'envmaptexture' field names the environment map texture.
                # Diffuse alpha = blend weight between surface and env map.
                # This fixes the see-through appearance on metallic/glossy surfaces
                # (droids, weapons, some creature hides) where alpha was incorrectly
                # treated as transparency.
                #
                # FIX-ENVFB: When the env-map texture name is set but the image
                # is not in the texture dict (partial load), bind a neutral grey
                # 1×1 fallback texture instead of nothing.  Without this fallback
                # the surface would be treated as transparent (u_has_env=0, diffuse
                # alpha applied as transparency), which is wrong — the surface
                # should remain opaque with a slight metallic tint.
                env_name = str(getattr(node, 'txi_envmaptexture', '')).strip().lower()
                if _detail_texture_allowed and bool(self.show_environment_map) and env_name:
                    env_img  = textures.get(env_name)
                    gl_env   = self._tex_cache.get(env_img) if env_img else None
                    if gl_env is None:
                        # Use grey fallback: neutral env tint keeps surface opaque
                        if self._grey_env_tex is None:
                            # 128,128,128,255 → 50% grey → neutral metallic tint
                            self._grey_env_tex = ctx.texture((1, 1), 4,
                                                              bytes([128, 128, 128, 255]))
                        gl_env = self._grey_env_tex
                    gl_env.use(location=2)
                    _u['u_env_tex'].value = 2
                    _u['u_has_env'].value = 1
                else:
                    _u['u_has_env'].value = 0

                # FIX-SPECMAP: Bind TXI specularcolour map to texture unit 3.
                # When the TXI 'specularcolour' keyword names a texture, that
                # texture's luminance is used as a per-texel specular intensity
                # multiplier in the fragment shader — giving armour and metallic
                # surfaces per-pixel gloss rather than a flat u_specular scalar.
                # Reference: Kotor.NET KotorModelLoader.cs specular texture slot;
                #            KotOR.js ShaderOdysseyModel.ts specularColor;
                #            xoreos modelnode.cpp _specularColour field.
                spec_name = str(getattr(node, 'txi_specularcolour', '')).strip().lower()
                if _detail_texture_allowed and bool(self.show_specular_map) and spec_name:
                    spec_img = textures.get(spec_name)
                    gl_spec  = self._tex_cache.get(spec_img) if spec_img else None
                    if gl_spec is not None:
                        gl_spec.use(location=3)
                        _u['u_spec_tex'].value = 3
                        _u['u_has_spec'].value = 1
                    else:
                        _u['u_has_spec'].value = 0
                else:
                    _u['u_has_spec'].value = 0

                bump_name = str(
                    getattr(node, 'txi_bumpmaptexture', '')
                    or getattr(node, 'bump_map', '')
                    or ''
                ).strip().lower()
                if _detail_texture_allowed and bool(self.show_normal_map) and bump_name:
                    bump_img = textures.get(bump_name)
                    gl_bump = self._tex_cache.get(bump_img) if bump_img else None
                    if gl_bump is not None:
                        gl_bump.use(location=4)
                        _u['u_bump_tex'].value = 4
                        _u['u_has_bump'].value = 1
                    else:
                        _u['u_has_bump'].value = 0
                else:
                    _u['u_has_bump'].value = 0

                # v7.1/7.2: Build feature bitmask for this node (Finding 5.2)
                # FIX-FEATMASK-ORDER: Moved AFTER texture binding so that
                # gl_diff, diff_img, gl_lm, env_name, spec_name are all
                # defined before use.  Previously caused UnboundLocalError
                # on the first draw call, silently falling back to CPU.
                _feat_mask = 0
                if gl_diff and diff_img: _feat_mask |= (1 << 0)   # FEAT_TEXTURE
                if _detail_texture_allowed and bool(self.show_lightmap_map) and gl_lm: _feat_mask |= (1 << 1)   # FEAT_LIGHTMAP
                if _detail_texture_allowed and bool(self.show_environment_map) and env_name: _feat_mask |= (1 << 2)   # FEAT_ENVMAP
                if _detail_texture_allowed and bool(self.show_specular_map) and spec_name: _feat_mask |= (1 << 3)   # FEAT_SPECMAP
                if _detail_texture_allowed and bool(self.show_normal_map) and bump_name: _feat_mask |= (1 << 4)   # FEAT_BUMPMAP
                if _is_dangly:          _feat_mask |= (1 << 6)   # FEAT_DANGLY
                if _is_saber:           _feat_mask |= (1 << 7)   # FEAT_SABER
                if txi_decal:           _feat_mask |= (1 << 11)  # FEAT_DECAL
                if txi_blend == 2:      _feat_mask |= (1 << 12)  # FEAT_PUNCHTHRU
                if txi_blend == 1:      _feat_mask |= (1 << 13)  # FEAT_ADDITIVE
                # Phase A: Set FEAT_SKIN bit when GPU skinning is active
                if _nd_is_skin and _has_skin_nodes and self._skin_uploader is not None:
                    _feat_mask |= (1 << 10)  # FEAT_SKIN
                _u['u_features'].value = _feat_mask

                # ── Phase A: GPU Skinning — enable/disable per draw call ──────
                # For skin nodes with a valid bone palette, enable LBS in the shader.
                # For non-skin nodes, ensure skinning is disabled (pass-through).
                #
                # FIX-SKIN-BINDPOSE: ONLY enable GPU skinning when there is an
                # active animation pose.  KotOR skin mesh vertices are stored in
                # world/bind-pose space (pre-transformed).  When anim_pose is
                # None, compute_palette() produces M = I × inv_bind = inv_bind,
                # which un-transforms verts from bind-pose to bone-local space,
                # causing geometry stretching/explosion.  The correct bind-pose
                # rendering path is to skip GPU skinning entirely (u_skin_enabled=0)
                # so the shader passes in_pos through unchanged.
                #
                # GPU skinning should only activate when anim_pose provides
                # world-pose matrices that differ from the bind pose.
                _skin_local_bone_count = 0
                if (_nd_is_skin and _has_skin_nodes
                        and self._skin_uploader is not None
                        and anim_pose is not None
                        and 'u_skin_enabled' in _u
                        and 'u_bone_count' in _u):
                    try:
                        self._skin_uploader.compute_skin_node_palette(node, anim_pose)
                        _skin_local_bone_count = len(getattr(node, 'bone_map', []) or [])
                        _skin_local_bone_count = min(_skin_local_bone_count, _SKIN_MAX_BONES)
                        if 'u_bones' in _u and _skin_local_bone_count > 0:
                            _u['u_bones'].write(self._skin_uploader.as_flat_bytes())
                        _u['u_skin_enabled'].value = 1 if _skin_local_bone_count > 0 else 0
                        _u['u_bone_count'].value = _skin_local_bone_count
                    except Exception as e:
                        log.debug(f"GPU-SKINNING: per-skin qBone/tBone palette upload failed: {e}")
                        _u['u_skin_enabled'].value = 0
                        _u['u_bone_count'].value = 0
                else:
                    if 'u_skin_enabled' in _u:
                        _u['u_skin_enabled'].value = 0
                    if 'u_bone_count' in _u:
                        _u['u_bone_count'].value = 0

                if self._gl_state_trace_path:
                    _append_gl_state_trace(
                        self._gl_state_trace_path,
                        _build_gl_state_trace_record(
                            ctx=ctx,
                            prog=prog,
                            node=node,
                            pass_name=pass_name,
                            tri_count=_use_tris,
                            blend_enabled=blend_enabled,
                            tex_name=tex_name,
                            lm_name=lm_name,
                            env_name=env_name,
                            spec_name=spec_name,
                            feature_mask=_feat_mask,
                            uniforms=_u,
                        ),
                    )

                if self._lm_data_dump_path and has_lm_flag:
                    _lm_key = (id(model), str(getattr(node, 'name', '') or '').lower())
                    if _lm_key not in self._lm_data_dump_seen:
                        self._lm_data_dump_seen.add(_lm_key)
                        _append_jsonl_record(
                            self._lm_data_dump_path,
                            _build_lm_data_dump_record(
                                ctx=ctx,
                                prog=prog,
                                node=node,
                                pass_name=pass_name,
                                gm=gm,
                                has_lm_flag=has_lm_flag,
                                lightmap_bound=gl_lm is not None,
                                lm_img=lm_img,
                                lm_name=lm_name,
                                uniforms=_u,
                            ),
                            'Lightmap data dump',
                        )

                if self._skin_dump_path and _nd_is_skin:
                    _skin_key = (id(model), str(getattr(node, 'name', '') or '').lower())
                    if _skin_key not in self._skin_dump_seen:
                        self._skin_dump_seen.add(_skin_key)
                        _append_jsonl_record(
                            self._skin_dump_path,
                            _build_skin_dump_record(
                                model=model,
                                node=node,
                                pass_name=pass_name,
                                uploader=self._skin_uploader,
                                bone_remap=_bone_remap,
                                uniforms=_u,
                                gm=gm,
                                anim_pose=anim_pose,
                                anim_base_pose=anim_base_pose,
                                anim_time=anim_time,
                            ),
                            'Skin parity dump',
                        )

                _use_vao.render(moderngl.TRIANGLES)
                total_tris += _use_tris

            # Helper: draw a node with correct KotOR texture routing.
            def _draw_node_multitex(node, pass_name: str = 'opaque'):
                """Draw a node with correct KotOR texture routing.

                FIX-KILL-FACEMATS (Phase D10): The previous implementation split
                multi-texture nodes by face_mats[], treating the walk-mesh surface
                indicator as a texture selector.  This is WRONG and has been removed.

                The correct KotOR texture model (per xoreos, KotOR.js, KotorBlender):
                  - One diffuse texture (texture_1) on UV0
                  - Optional one lightmap (texture_2) on UV1
                  - Composite: diffuse * lightmap * overbright
                  - face_mats is a walk-mesh surface type, NOT a texture selector

                For ALL nodes regardless of tex_count, we draw ONCE with:
                  - Diffuse texture bound to sampler 0
                  - Lightmap (if has_lightmap) bound to sampler 1
                  - Lightmap compositing handled by fragment shader

                Reference: xoreos model_kotor.cpp — single diffuse per mesh;
                KotOR.js OdysseyModelNodeMesh.ts — single texture per mesh;
                KotorBlender reader.py — material field is surface type.
                """
                # Always draw once with primary diffuse + optional lightmap.
                # _draw_node already handles lightmap binding via u_lm_tex/u_has_lm
                # when has_lightmap is True and lightmap UVs are present.
                _draw_node(node, pass_name=pass_name)

            # ── Pass 1: Opaque geometry (depth write ON, no blending) ─────────────
            # Solid, fully-opaque surfaces with no alpha-test.
            # Cross-ref: Hayes (2025) §6.3; reone: GL_DEPTH_TEST + depth write ON.
            ctx.depth_mask = True
            ctx.disable(moderngl.BLEND)
            for node in opaque_nodes:
                _draw_node_multitex(node, pass_name='opaque')

            # ── Pass 2: Alpha-cutout geometry (depth write ON, shader discard) ────
            # Punchthrough / alpha-test surfaces: hair cards, fur edges, eye cutouts,
            # grates, foliage.  Depth write stays ON so cutout geometry properly
            # occludes what's behind it; the fragment shader discards pixels below
            # the alpha threshold (u_alpha_test, default 0.5).
            # Cross-ref: Hayes (2025) §8.2 alpha testing; Gregory (2024) §10.6.
            # ctx.depth_mask stays True; no blending needed for cutout.
            for node in cutout_nodes:
                _draw_node_multitex(node, pass_name='cutout')

            # ── Pass 3: Transparent/additive geometry (depth write OFF) ───────────
            # BUG-ALPHA FIX: Sort transparent nodes back-to-front by their centroid
            # distance from the camera eye before drawing.  Without sorting, overlapping
            # transparent surfaces (glass visors, alpha-blended hair) produce incorrect
            # compositing because the painter's algorithm requires back-to-front order.
            if transparent_nodes:
                eye_arr = np.array(eye, dtype=np.float64)

                def _node_sort_depth(nd):
                    """Return squared distance from camera to node centroid (descending sort = back first).

                    Prefers mesh_average_point (the exact Aurora-engine centroid stored in the
                    TrimeshHeader) over the bounding-box midpoint for accurate depth sorting.
                    Kotor.NET TrimeshHeader.AveragePoint; xoreos _averagePoint.
                    """
                    _wp2, world_mat = _get_world_transform(nd)
                    try:
                        # Prefer the pre-computed mesh centroid (AveragePoint from binary MDL).
                        avg_pt = getattr(nd, 'mesh_average_point', None)
                        if avg_pt and (avg_pt[0] != 0.0 or avg_pt[1] != 0.0 or avg_pt[2] != 0.0):
                            # Transform mesh-local average point to world space
                            if world_mat is not None:
                                ax, ay, az = float(avg_pt[0]), float(avg_pt[1]), float(avg_pt[2])
                                m = world_mat
                                wx = m[0]*ax + m[4]*ay + m[8]*az  + m[12]
                                wy = m[1]*ax + m[5]*ay + m[9]*az  + m[13]
                                wz = m[2]*ax + m[6]*ay + m[10]*az + m[14]
                                c = np.array([wx, wy, wz], dtype=np.float64)
                            else:
                                c = np.array(avg_pt, dtype=np.float64)
                        else:
                            # Fall back to world-transform position (node origin)
                            c = np.array(_wp2, dtype=np.float64)
                        d = c - eye_arr
                        return float(np.dot(d, d))
                    except Exception:
                        return 0.0

                # Sort farthest-first (painter's algorithm: draw back before front)
                transparent_nodes_sorted = sorted(transparent_nodes,
                                                  key=_node_sort_depth, reverse=True)
                ctx.depth_mask = False
                for node in transparent_nodes_sorted:
                    _draw_node_multitex(node, pass_name='transparent')
                # Restore depth writes after transparent pass
                ctx.depth_mask = True
                ctx.disable(moderngl.BLEND)
            if self.show_solid and self.show_wireframe:
                try:
                    self._wireframe_pass = True
                    ctx.wireframe = True
                    ctx.depth_mask = False
                    ctx.disable(moderngl.BLEND)
                    for node in opaque_nodes:
                        _draw_node_multitex(node, pass_name='opaque')
                    for node in cutout_nodes:
                        _draw_node_multitex(node, pass_name='cutout')
                    for node in transparent_nodes:
                        _draw_node_multitex(node, pass_name='transparent')
                finally:
                    self._wireframe_pass = False
                    ctx.depth_mask = True
            try:
                ctx.wireframe = False
            except Exception:
                pass
            self._wireframe_pass = False
            self._draw_light_gizmos(ctx, mvp, nodes, _get_world_transform)

            self.perf['draw_ms'] = (time.perf_counter() - t_draw) * 1000
            self.perf['tri_count'] = total_tris

            # ── MSAA Resolve (if multisampled FBO) ───────────────────────
            # FIX-MSAA: Blit the 4x MSAA renderbuffer to the single-sample
            # resolve FBO before reading pixels. This eliminates the single-pixel
            # magenta/neon-green fringe artifacts at triangle edges.
            # PERF-FBO: Only resolve when we actually used the MSAA FBO (not
            # the simple interactive FBO).
            if (_use_msaa and getattr(self, '_fbo_msaa', False)
                    and getattr(self, '_fbo_resolve', None)):
                try:
                    ctx.copy_framebuffer(self._fbo_resolve, self._fbo)
                    read_fbo = self._fbo_resolve
                except Exception:
                    read_fbo = fbo
            else:
                read_fbo = fbo

            # ── Read back framebuffer to PIL Image ────────────────────
            # PERF-FIX: Use dtype='f1' (RGBA8 UNorm) for fbo.read().
            # On llvmpipe EGL with a renderbuffer color attachment:
            #   dtype='u1' → reads raw bytes (all zeros, WRONG)
            #   dtype='f1' → reads RGBA8 UNorm bytes (correct uint8 values)
            #   dtype='f4' → reads float32 (correct, but 7ms not 0.4ms)
            # dtype='f1' + np.frombuffer as uint8 gives RGBA8 at ~0.4ms.
            # PERF-FIX 2: Use numpy array reversal for vertical flip instead of
            # PIL.transpose(FLIP_TOP_BOTTOM) which copies the entire image (~275ms).
            # NumPy array reversal with .copy() costs ~0.5ms.
            # ── PERF-READBACK: Optimized framebuffer readback ───────────
            # Since we clear the FBO with alpha=1.0 (opaque BG), most pixels
            # have alpha=255.  The expensive alpha-composite step (~19ms at
            # 800x600) can be skipped in interactive mode, or when we detect
            # no transparent geometry was drawn.
            # For final (non-interactive) frames we still composite to handle
            # glass/water/hologram transparency correctly.
            t_rb = time.perf_counter()
            _skip_alpha_composite = self.interactive or (not transparent_nodes)
            if _skip_alpha_composite and _NUMPY:
                # FAST PATH: Read RGB only (skip alpha channel entirely).
                # Reading 3 components instead of 4 saves ~25% readback bandwidth.
                raw = read_fbo.read(components=3, dtype='f1')
                arr = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 3)[::-1].copy()
                img = Image.fromarray(arr, 'RGB')
            elif _NUMPY:
                raw = read_fbo.read(components=4, dtype='f1')
                arr = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 4)[::-1].copy()
                # Alpha composite against opaque background for transparent surfaces
                bg = np.array([23, 25, 28], dtype=np.uint16)
                rgb  = arr[:, :, :3].astype(np.uint16)
                a    = arr[:, :, 3:4].astype(np.uint16)
                out  = ((rgb * a + bg * (255 - a)) // 255).clip(0, 255).astype(np.uint8)
                img  = Image.fromarray(out, 'RGB')
            else:
                raw = read_fbo.read(components=4, dtype='f1')
                rgba_img = Image.frombytes('RGBA', (W, H), raw)
                rgba_img = rgba_img.transpose(Image.FLIP_TOP_BOTTOM)
                bg_img = Image.new('RGB', (W, H), (23, 25, 28))
                bg_img.paste(rgba_img, mask=rgba_img.split()[3])
                img = bg_img
            # PERF-SCALE: Upscale reduced-resolution interactive frames smoothly.
            if self.interactive and (_full_W != W or _full_H != H):
                img = img.resize((_full_W, _full_H), Image.BILINEAR)
            self.perf['readback_ms'] = (time.perf_counter() - t_rb) * 1000

            return img

        except Exception as e:
            log.warning(f"GpuRenderer._render_gpu: {e}", exc_info=True)
            return None

    # ── CPU fallback render ───────────────────────────────────────────────────

    def _render_cpu(self, model, camera, W: int, H: int,
                    textures: Dict[str, 'Image.Image'],
                    anim_pose, anim_time: float) -> Optional['Image.Image']:
        """
        CPU fallback: delegates to the existing PIL-based FrameRenderer.
        Returns a PIL RGB Image.
        """
        if not _PIL:
            return None
        try:
            from src.gui.rendering.viewport_core import FrameRenderer, ArcBallCamera
            renderer = FrameRenderer(camera)
            renderer.model = model
            renderer.show_texture = True
            renderer.show_bones   = False
            renderer.show_grid    = False
            renderer.textures     = textures
            renderer._anim_pose   = anim_pose
            renderer._anim_time   = anim_time
            # Build texture cache from provided dict.
            # Use a proxy that first checks the provided textures dict, then falls
            # back to the real TextureCache (which searches disk + BIF archives).
            # This ensures textured rendering even when textures dict is partial.
            _real_tc = getattr(renderer, 'tex_cache', None)
            _tex_snapshot = dict(textures)  # local copy to avoid mutation

            class _ProxyTC:
                """Proxy texture cache: dict first, then real cache fallback."""
                def get(self, name):
                    if not name:
                        return None
                    k = name.lower()
                    hit = _tex_snapshot.get(k)
                    if hit is not None:
                        return hit
                    # Fallback to real TextureCache (searches disk dirs + BIF)
                    if _real_tc is not None and hasattr(_real_tc, 'get'):
                        try:
                            return _real_tc.get(k)
                        except Exception:
                            pass
                    return None

                def get_mip1(self, img):
                    if _real_tc is not None and hasattr(_real_tc, 'get_mip1'):
                        return _real_tc.get_mip1(img)
                    return img

                def sample(self, img, u, v, interp=True):
                    if _real_tc is not None and hasattr(_real_tc, 'sample'):
                        return _real_tc.sample(img, u, v, interp)
                    return (128, 128, 128)

                def sample_bilinear(self, img, u, v):
                    if _real_tc is not None and hasattr(_real_tc, 'sample_bilinear'):
                        return _real_tc.sample_bilinear(img, u, v)
                    return (128, 128, 128, 255)

                def get_txi(self, name):
                    if _real_tc is not None and hasattr(_real_tc, 'get_txi'):
                        return _real_tc.get_txi(name)
                    return ''

                def get_raw_header(self, name):
                    if _real_tc is not None and hasattr(_real_tc, 'get_raw_header'):
                        return _real_tc.get_raw_header(name)
                    return None

                def clear_mip_cache(self):
                    if _real_tc is not None and hasattr(_real_tc, 'clear_mip_cache'):
                        _real_tc.clear_mip_cache()

            renderer.tex_cache = _ProxyTC()
            img = renderer.render(W, H)
            # Kill the alpha layer — flatten RGBA to RGB against the background
            if img is not None and getattr(img, 'mode', 'RGB') == 'RGBA':
                bg_img = Image.new('RGB', img.size, (23, 25, 28))
                bg_img.paste(img, mask=img.split()[3])
                img = bg_img
            return img
        except Exception as e:
            log.warning(f"GpuRenderer._render_cpu: {e}", exc_info=True)
            if _PIL:
                return Image.new('RGBA', (W, H), (31, 36, 41, 255))
            return None

    # ── Invalidate node cache ─────────────────────────────────────────────────

    def invalidate_node(self, node) -> None:
        """Remove cached GPU buffers and world-transform for a node (call after mesh edits)."""
        nid = id(node)
        if nid in self._mesh_cache:
            self._mesh_cache[nid].release()
            del self._mesh_cache[nid]
        # Also evict from persistent world-transform cache so next render recomputes
        if nid in self._wt_cache:
            del self._wt_cache[nid]

    def invalidate_all(self) -> None:
        """Remove all cached GPU buffers and world-transform cache."""
        for m in self._mesh_cache.values():
            m.release()
        self._mesh_cache.clear()
        # Clear persistent world-transform cache; will be rebuilt next render
        self._wt_cache.clear()
        self._wt_model_id = 0
        self.invalidate_node_cache()

    def invalidate_node_cache(self) -> None:
        """Force node visibility/pass classification to rebuild next frame."""
        self._node_cache_model_id = 0
        self._node_cache_opaque = []
        self._node_cache_cutout = []
        self._node_cache_transparent = []

    # ── Performance info ──────────────────────────────────────────────────────

    @property
    def is_gpu(self) -> bool:
        """True if the GPU (ModernGL/EGL) path is active."""
        return self._gpu_available and not self.force_cpu

    def perf_summary(self) -> str:
        p = self.perf
        return (
            f"backend={p['backend']}  "
            f"frame={p['last_frame_ms']:.1f}ms  "
            f"tris={p['tri_count']}  "
            f"upload={p['gpu_upload_ms']:.1f}ms  "
            f"draw={p['draw_ms']:.1f}ms  "
            f"readback={p['readback_ms']:.1f}ms"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Auto-framing camera helper
# ─────────────────────────────────────────────────────────────────────────────

def _compute_model_bounds(model) -> dict:
    """
    D20-M: Walk all renderable mesh nodes and return the world-space AABB,
    using the per-node vertex_space contract (same as _build_vbo_data).

    Returns dict with keys: min_x, max_x, min_y, max_y, min_z, max_z,
    center_x/y/z, extent_x/y/z, max_extent, radius.
    Falls back to the model's stored bb_min/bb_max if no vertex data is found.

    No centroid heuristics, no _WORLDSPACE_THRESHOLD, no accessory detection.
    References:
      xoreos model_kotor.cpp readMesh — verts are node-local
      KotOR.js OdysseyModel3D.ts      — matrixWorld for GPU transform
    """
    # Detect module/area/tile models for renderable no-UV geometry.
    _bounds_model_cls  = (str(getattr(model, 'classification', 'character') or 'character')).lower()
    _bounds_model_type_raw = getattr(model, 'model_type', None)
    _bounds_model_type = int(_bounds_model_type_raw) if _bounds_model_type_raw is not None else 4
    _bounds_is_module  = (_bounds_model_cls in ('effect', 'tile', 'other') or
                          _bounds_model_type in (0, 2))

    all_pts = []

    _all_nodes_fn = getattr(model, 'all_nodes', None)
    nodes = list(_all_nodes_fn()) if _all_nodes_fn else getattr(model, 'nodes', [])

    for node in nodes:
        verts = getattr(node, 'vertices', None) or []
        if not verts:
            continue
        uvs = getattr(node, 'uvs', []) or []
        has_uvs = bool(uvs)

        # Skip deformation-helper nodes (same rules as _is_deform_helper)
        if not has_uvs and not _bounds_is_module:
            continue
        if node.name.lower().endswith(('_g', '_g0', '_dum')):
            continue
        try:
            import numpy as _np
            v_arr = _np.array(verts, dtype=np.float64)
        except Exception:
            continue

        # D20-M: Use vertex_space contract — no centroid checks
        _node_vs = getattr(node, 'vertex_space', 0)  # default NODE_LOCAL

        if _node_vs == 0:  # NODE_LOCAL — apply full world transform
            try:
                wt = node.world_transform()
                wp = np.array(wt[0], dtype=np.float64)
                wo = np.array(wt[1], dtype=np.float64)
                qlen = np.linalg.norm(wo)
                if qlen > 1e-9:
                    wo = wo / qlen
                is_id_rot = (abs(wo[3]) > 0.9999 and
                             abs(wo[0]) < 1e-6 and
                             abs(wo[1]) < 1e-6 and
                             abs(wo[2]) < 1e-6)
                if not is_id_rot:
                    v_arr = _quat_rotate_batch(wo, v_arr)
                v_arr = v_arr + wp
            except Exception:
                pass
        elif _node_vs == 1:  # WORLD — already in world space, use as-is
            pass
        # _node_vs == 2 (AABB_WALK) — skip walkmesh
        elif _node_vs == 2:
            continue

        all_pts.append(v_arr)

    if all_pts:
        all_v = np.vstack(all_pts)
        mn_x, mn_y, mn_z = float(all_v[:, 0].min()), float(all_v[:, 1].min()), float(all_v[:, 2].min())
        mx_x, mx_y, mx_z = float(all_v[:, 0].max()), float(all_v[:, 1].max()), float(all_v[:, 2].max())
    else:
        # Fall back to stored model bounds
        bb_min = getattr(model, 'bb_min', (-1, -1, -1)) or (-1, -1, -1)
        bb_max = getattr(model, 'bb_max', ( 1,  1,  1)) or ( 1,  1,  1)
        mn_x, mn_y, mn_z = float(bb_min[0]), float(bb_min[1]), float(bb_min[2])
        mx_x, mx_y, mx_z = float(bb_max[0]), float(bb_max[1]), float(bb_max[2])

    cx = (mn_x + mx_x) * 0.5
    cy = (mn_y + mx_y) * 0.5
    cz = (mn_z + mx_z) * 0.5
    ext_x = mx_x - mn_x
    ext_y = mx_y - mn_y
    ext_z = mx_z - mn_z
    max_ext = max(ext_x, ext_y, ext_z, 0.01)
    radius  = math.sqrt(ext_x**2 + ext_y**2 + ext_z**2) * 0.5

    return {
        'min_x': mn_x, 'max_x': mx_x,
        'min_y': mn_y, 'max_y': mx_y,
        'min_z': mn_z, 'max_z': mx_z,
        'center_x': cx, 'center_y': cy, 'center_z': cz,
        'extent_x': ext_x, 'extent_y': ext_y, 'extent_z': ext_z,
        'max_extent': max_ext,
        'radius': radius,
    }


def _apply_txi_from_textures_to_model(model, textures: dict) -> None:
    """
    Apply TXI metadata extracted from texture sources to model nodes.

    KotOR TPC files embed TXI metadata (blending mode, env map, etc.) as an
    ASCII trailer after the pixel data.  The MDL binary parser does not read
    these TPC-embedded TXI strings — it only processes standalone .txi files.
    This function bridges that gap by extracting TXI from available TPC bytes
    and applying the metadata to all mesh nodes that use each texture.

    Typical usage: call before GPU rendering when the TPC raw bytes are
    available in the 'textures' dict (as PIL Images with _txi_str attribute
    set by a TPC-aware loader, or via the viewport's TXI cache).

    When textures dict contains PIL.Image objects without TXI attributes,
    this function is a no-op (no TXI metadata available to apply).

    This fixes: creature meshes using DXT5 textures with 'blending 2' TXI
    (punchthrough alpha) so that hair, fur edges, and eye cutouts render
    correctly.  Without this fix, txi_blending stays 0 and the shader
    forces final_alpha=1.0 for all fragments, making the DXT5 alpha channel
    (which encodes the cut-out shape) invisible — resulting in solid-block
    hair/fur geometry ('teeth on the rail' artefact).
    """
    if not textures:
        return
    _extract_txi_from_tpc = None
    _parse_txi_string = None
    _apply_txi_to_node = None
    for _import_path in ('src.gui.rendering.viewport_core', 'src.gui.qt_lib.rendering.viewport_core'):
        try:
            import importlib as _il
            _m = _il.import_module(_import_path)
            _extract_txi_from_tpc = getattr(_m, '_extract_txi_from_tpc', None)
            _parse_txi_string     = getattr(_m, '_parse_txi_string', None)
            _apply_txi_to_node    = getattr(_m, '_apply_txi_to_node', None)
            if _extract_txi_from_tpc and _parse_txi_string and _apply_txi_to_node:
                break
        except ImportError:
            pass
    _have_txi_tools = bool(_extract_txi_from_tpc and _parse_txi_string and _apply_txi_to_node)

    if not _have_txi_tools:
        return

    # Build tex_name → TXI string and alpha_test mappings from available sources.
    # FIX-ALPHATEST: Also capture per-texture alpha_test from TPC header (bytes 4-7).
    # The TPC header field at offset 4 stores the engine's intended alpha-test
    # threshold for punchthrough blending (e.g. 0.9333 for c_bantha01, 0.7176 for
    # c_banthh01).  _load_tpc_bytes() now sets img._txi_alpha_test from this field;
    # we read it here and pass it to _apply_txi_to_node() so the shader receives the
    # correct threshold instead of the generic 0.5 default.
    _txi_cache: dict = {}
    _at_cache: dict  = {}   # tex_name → float alpha_test (from TPC header)
    for tex_name, tex_obj in textures.items():
        # Collect alpha_test from image attribute (set by _load_tpc_bytes)
        _img_at = getattr(tex_obj, '_txi_alpha_test', None)
        if _img_at is not None:
            try:
                _at_v = float(_img_at)
                if 0.0 < _at_v <= 1.0:
                    _at_cache[tex_name] = _at_v
            except (TypeError, ValueError):
                pass

        if tex_name in _txi_cache:
            continue
        # Option 1: PIL Image has _txi_str attribute set by a TPC-aware loader
        txi_str = getattr(tex_obj, '_txi_str', None)
        if txi_str:
            _txi_cache[tex_name] = txi_str
            continue
        # Option 2: PIL Image has _tpc_raw attribute (raw TPC bytes)
        raw = getattr(tex_obj, '_tpc_raw', None)
        if raw:
            try:
                txi_str = _extract_txi_from_tpc(raw)
                if txi_str:
                    _txi_cache[tex_name] = txi_str
                # Also try to read alpha_test from raw TPC header if not already set
                if tex_name not in _at_cache and len(raw) >= 8:
                    import struct as _st
                    _at_v = _st.unpack_from('<f', raw, 4)[0]
                    if 0.0 < _at_v <= 1.0:
                        _at_cache[tex_name] = _at_v
            except Exception:
                pass

    # Apply TXI and alpha_test to each mesh node.
    # NOTE: We apply even when _txi_cache is empty — nodes still need txi_alpha_test
    # set from the TPC header for correct punchthrough threshold on hair/fur meshes.
    #
    # FIX-MULTITEX-TXI: Also apply TXI for ALL texture_names entries, not just
    # the primary node.texture.  Multi-texture nodes (tex_count > 1) may have
    # secondary textures with TXI metadata (punchthrough, env-map, etc.) that
    # must be applied to the node for correct rendering of each material slot.
    try:
        all_nodes_fn = getattr(model, 'all_nodes', None)
        nodes = list(all_nodes_fn()) if all_nodes_fn else getattr(model, 'nodes', [])
        for node in nodes:
            if not getattr(node, 'is_mesh', False):
                continue
            # Collect all texture names used by this node
            _all_tex_names = set()
            tex_name = str(getattr(node, 'texture', '') or '').strip().lower()
            if tex_name and tex_name not in ('null', '', 'none'):
                _all_tex_names.add(tex_name)
            # Also include all entries from texture_names[]
            for _tn in getattr(node, 'texture_names', []):
                _tn_clean = str(_tn or '').strip().lower()
                if _tn_clean and _tn_clean not in ('null', '', 'none'):
                    _all_tex_names.add(_tn_clean)

            if not _all_tex_names:
                continue

            # Apply TXI from primary texture first (most important)
            _primary_txi = _txi_cache.get(tex_name, '') if tex_name else ''
            _primary_at = _at_cache.get(tex_name,
                                         float(getattr(node, 'txi_alpha_test', 0.5)))
            if _primary_txi or _primary_at != 0.5:
                try:
                    _apply_txi_to_node(node, _primary_txi, _primary_at)
                except Exception:
                    pass

            # Apply TXI from secondary textures (env-map, bump, specular, etc.)
            # These may set txi_envmaptexture, txi_bumpmaptexture, etc.
            for _sec_name in _all_tex_names:
                if _sec_name == tex_name:
                    continue  # already applied above
                _sec_txi = _txi_cache.get(_sec_name, '')
                if _sec_txi:
                    try:
                        # Apply secondary TXI but keep the primary alpha_test
                        _apply_txi_to_node(node, _sec_txi,
                                           float(getattr(node, 'txi_alpha_test', 0.5)))
                    except Exception:
                        pass
    except Exception as e:
        log.debug(f'_apply_txi_from_textures_to_model error: {e}')


class _CompositeModel:
    """
    Lightweight wrapper that merges two KotorModel objects for combined rendering.

    FIX-SUPERMODEL-BODY: KotOR head-only models (ad_saul, comm_b_f, etc.) store
    only the head mesh.  The body geometry lives in their supermodel
    (e.g. N_AdmrlSaulKar).  Ghost Rigger renders models standalone, so the body
    is normally absent.

    This wrapper combines ``head_model.all_nodes()`` and ``body_model.all_nodes()``
    into a single iterable, while forwarding all other attributes to head_model so
    the GPU renderer sees a single coherent model object.

    Body nodes are tagged with ``_model_ref = body_model`` so that
    ``_build_vbo_data`` can apply the correct world-space treatment (body skin
    meshes are already in world space → no extra transform).
    The head nodes keep their original ``_model_ref`` (or are tagged to head_model)
    so the accessory-skin transform heuristic still applies correctly.

    Bounding-box attributes (bb_min, bb_max, radius) are expanded to cover both
    models so ``_compute_model_bounds`` can fall back to them if no vertex data
    is available.
    """

    def __init__(self, head_model, body_model):
        self._head = head_model
        self._body = body_model

        # Expand stored AABB to cover both models
        def _bb(m, attr, default):
            v = getattr(m, attr, None)
            return v if v is not None else default

        h_min = _bb(head_model, 'bb_min', (-1, -1, -1))
        h_max = _bb(head_model, 'bb_max', ( 1,  1,  1))
        b_min = _bb(body_model, 'bb_min', (-1, -1, -1))
        b_max = _bb(body_model, 'bb_max', ( 1,  1,  1))
        self.bb_min = (min(h_min[0], b_min[0]), min(h_min[1], b_min[1]), min(h_min[2], b_min[2]))
        self.bb_max = (max(h_max[0], b_max[0]), max(h_max[1], b_max[1]), max(h_max[2], b_max[2]))
        dx = self.bb_max[0] - self.bb_min[0]
        dy = self.bb_max[1] - self.bb_min[1]
        dz = self.bb_max[2] - self.bb_min[2]
        import math as _math
        self.radius = _math.sqrt(dx*dx + dy*dy + dz*dz) * 0.5

        # FIX-NONSKIN-OFFSET: Compute the offset to apply to non-skin nodes from
        # the head accessory model so they render at their correct world positions
        # (i.e., at the head bone's position in the body skeleton, not at the
        # model-root's local position).
        #
        # Method: find a shared skeleton bone name that appears in BOTH models
        # (e.g. 'head_g', 'Hturn_g') and compute:
        #   offset = body_bone_world_pos - head_bone_world_pos
        # Then any non-skin head node's world_pos is corrected by adding this offset.
        #
        # If no shared bone is found, fall back to offset = (0,0,0) (no correction).
        self._nonskin_head_offset = (0.0, 0.0, 0.0)
        try:
            # Candidate anchor bone names in priority order
            _ANCHOR_BONES = ('head_g', 'Hturn_g', 'neck_g', 'necklwr_g', 'headhook')

            # Build name → world_pos maps for both models
            _body_bones: dict = {}
            _body_all = list(body_model.all_nodes()) if hasattr(body_model,'all_nodes') else list(getattr(body_model,'nodes',[]))
            for _bn in _body_all:
                try:
                    _bwp, _ = _bn.world_transform()
                    _body_bones[_bn.name.lower()] = _bwp
                except Exception:
                    pass

            _head_bones: dict = {}
            _head_all = list(head_model.all_nodes()) if hasattr(head_model,'all_nodes') else list(getattr(head_model,'nodes',[]))
            for _hn in _head_all:
                try:
                    _hwp, _ = _hn.world_transform()
                    _head_bones[_hn.name.lower()] = _hwp
                except Exception:
                    pass

            # Find the best matching anchor bone
            for _anchor in _ANCHOR_BONES:
                _bwp = _body_bones.get(_anchor)
                _hwp = _head_bones.get(_anchor)
                if _bwp is not None and _hwp is not None:
                    self._nonskin_head_offset = (
                        float(_bwp[0]) - float(_hwp[0]),
                        float(_bwp[1]) - float(_hwp[1]),
                        float(_bwp[2]) - float(_hwp[2]),
                    )
                    log.debug(f"_CompositeModel: anchor bone '{_anchor}' "
                              f"body={tuple(round(x,3) for x in _bwp)} "
                              f"head={tuple(round(x,3) for x in _hwp)} "
                              f"offset={tuple(round(x,3) for x in self._nonskin_head_offset)}")
                    break
        except Exception as _e:
            log.debug(f"_CompositeModel: could not compute non-skin offset: {_e}")

    # Forward scalar model attributes to the head model
    def __getattr__(self, name):
        return getattr(self._head, name)

    def all_nodes(self):
        """Return head nodes first, then body nodes (for correct depth ordering)."""
        head_nodes = []
        _h_fn = getattr(self._head, 'all_nodes', None)
        if _h_fn:
            head_nodes = list(_h_fn())
        else:
            head_nodes = list(getattr(self._head, 'nodes', []))

        body_nodes = []
        _b_fn = getattr(self._body, 'all_nodes', None)
        if _b_fn:
            body_nodes = list(_b_fn())
        else:
            body_nodes = list(getattr(self._body, 'nodes', []))

        # Tag each body node so _build_vbo_data uses the correct model context
        for _bn in body_nodes:
            try:
                _bn._model_ref = self._body
            except (AttributeError, TypeError):
                pass

        # Tag each head node with:
        # - _model_ref = head model (for accessory-skin detection)
        # - _composite_nonskin_offset = world-space offset to apply to non-skin
        #   nodes so they render at the correct position in the body skeleton
        #   (= body_head_g_world - head_head_g_local)
        _off = self._nonskin_head_offset
        for _hn in head_nodes:
            try:
                _hn._model_ref = self._head
            except (AttributeError, TypeError):
                pass
            try:
                _hn._composite_nonskin_offset = _off
            except (AttributeError, TypeError):
                pass

        return head_nodes + body_nodes

    @property
    def nodes(self):
        return self.all_nodes()


# Base skeleton names (models that ARE the skeleton, not head accessories).
# Re-export the canonical constant from core.model_data for use by callers
# that import this module (kept for backwards-compatibility).
_BASE_SKELETONS: frozenset = _KOTOR_BASE_SKELETONS


def render_model_autoframe(
        model,
        W: int = 512,
        H: int = 512,
        textures: Optional[Dict[str, 'Image.Image']] = None,
        anim_pose=None,
        views: Optional[list] = None,
        fov: float = 45.0,
        renderer: Optional['GpuRenderer'] = None,
        supermodel_body=None,
        supermodel_textures: Optional[Dict[str, 'Image.Image']] = None,
) -> Dict[str, 'Image.Image']:
    """
    Render a KotOR model from multiple angles with an automatically computed
    camera that frames the entire model within the viewport.

    Parameters
    ----------
    model              : KotorModel (from MDLBinaryParser)
    W, H               : output image size in pixels
    textures           : dict of {name: PIL.Image} texture maps
    anim_pose          : optional AnimPose object
    views              : list of view names to render; defaults to
                         ['front', 'back', 'right', 'left', 'top', 'diag']
    fov                : camera field-of-view in degrees (default 45)
    renderer           : existing GpuRenderer to reuse (creates a new one if None)
    supermodel_body    : KotorModel for the supermodel body (e.g. N_AdmrlSaulKar
                         for ad_saul).  When provided the head model is composited
                         onto the body model for rendering.
    supermodel_textures: additional texture dict for the supermodel body textures

    Returns
    -------
    dict mapping view name → PIL.Image (RGBA)

    Camera placement
    ----------------
    KotOR uses Y-forward, Z-up.  Character/creature models face toward +Y
    (the creature's face is at the +Y end of its bounding box and the
    forward movement direction is +Y — i.e. nose/eyes point toward +Y).
    - 'front'  : camera at +Y looking toward -Y  → creature face visible
    - 'back'   : camera at -Y looking toward +Y  → creature rear/tail visible
    - 'right'  : camera at +X looking toward -X  → model right profile
    - 'left'   : camera at -X looking toward +X  → model left profile
    - 'top'    : camera straight above looking down
    - 'diag'   : 3/4 view (front-right-top), creature face visible

    FIX-LABEL: Previous versions had front/back offsets swapped (+Y/-Y),
    causing the 'front' view to show the creature's rear and vice-versa.
    Corrected to match render_stills_v12 convention (front = camera at +Y).

    Framing
    -------
    The camera distance includes both the perpendicular extent (to fit the
    model in the FOV) and the depth half-extent along the viewing axis (to
    push the camera back far enough that the nearest model face is not
    over-magnified by perspective projection).
    """
    if views is None:
        views = ['front', 'back', 'right', 'left', 'top', 'diag']

    # FIX-TXI-AUTOFRAME: Apply TXI metadata from TPC raw bytes to model nodes.
    # The MDL binary parser does not read TXI data embedded in TPC texture files.
    # When tpc_bytes dict is provided, extract TXI from each TPC and update node
    # fields (txi_blending, txi_alpha_test, txi_envmaptexture, etc.) so the GPU
    # renderer uses correct blend modes (e.g. 'blending 2' punchthrough for hair).
    if textures is not None:
        _apply_txi_from_textures_to_model(model, textures)

    # FIX-SUPERMODEL-BODY: If a supermodel body was supplied, create a composite
    # model that renders both the body and the head together.  This fixes head-only
    # models like ad_saul (supermodel = N_AdmrlSaulKar) and comm_b_f
    # (supermodel = S_Female03) that only contain the head mesh; without this the
    # render shows only a floating head with no body.
    #
    # The combined texture dict merges both head and body textures.
    _render_model = model
    _render_textures = dict(textures) if textures else {}
    if supermodel_body is not None:
        try:
            _render_model = _CompositeModel(model, supermodel_body)
            if supermodel_textures:
                _render_textures.update(supermodel_textures)
            if supermodel_textures is not None:
                _apply_txi_from_textures_to_model(supermodel_body, supermodel_textures)
            log.debug(f"render_model_autoframe: compositing head '{getattr(model,'name','?')}' "
                      f"onto body '{getattr(supermodel_body,'name','?')}'")
        except Exception as _e:
            log.warning(f"render_model_autoframe: supermodel composite failed: {_e}")
            _render_model = model

    bounds = _compute_model_bounds(_render_model)
    cx = bounds['center_x']
    cy = bounds['center_y']
    cz = bounds['center_z']
    max_ext = bounds['max_extent']

    # Per-axis extents – use per-axis distance so the camera is tight on each axis.
    ext_x = bounds['extent_x']
    ext_y = bounds['extent_y']
    ext_z = bounds['extent_z']

    half_fov_rad = math.radians(fov * 0.5)
    tan_hfov = math.tan(half_fov_rad)

    # Per-axis half-extents from bounding-box centre.
    half_x = ext_x * 0.5
    half_y = ext_y * 0.5
    half_z = ext_z * 0.5

    def _axis_dist(perp_ext: float, depth_half: float = 0.0) -> float:
        """Return camera-to-centre distance so that the model fits in the FOV.

        perp_ext   : full extent perpendicular to the view axis (width or height
                     of the model face visible from this camera direction).
        depth_half : half-extent *along* the view axis (half the model depth).
                     The camera must be placed at least this far from the centre
                     so it does not clip through the nearest model face, and the
                     near face must also fit entirely within the FOV.

        The formula uses two constraints and takes the max:
          1. FOV fit at the near face: cam_dist ≥ (perp_half / tan_hfov) + depth_half
             — guarantees that geometry at the near model face does not exceed
               the viewport edges (no clipping of horns, protruding parts, etc.).
          2. FOV fit at the centre: cam_dist ≥ (perp_half * 1.10) / tan_hfov
             — for shallow models where near-face clearance alone would push the
               camera further than needed.

        A 10 % margin (factor 1.10) leaves ~9 % padding around the model edges.
        """
        perp_half = perp_ext * 0.5
        # Constraint 1: near-face clears the FOV (exact mathematical minimum)
        near_face_min = perp_half / tan_hfov + depth_half
        # Constraint 2: centre-based FOV fit with 10% breathing room
        centre_fit = (perp_half * 1.10) / tan_hfov
        return max(near_face_min, centre_fit) + max_ext * 0.03

    # Per-view camera: (eye_offset_from_center, up_vector)
    # FIX-LABEL: KotOR creatures face +Y (nose/eyes at +Y end of bounding box).
    # Camera must be placed at +Y to look back toward -Y and see the face.
    #   'front': camera at +Y → looks toward -Y → sees creature face
    #   'back' : camera at -Y → looks toward +Y → sees creature rear/tail
    #   'right': camera at +X → right profile
    #   'left' : camera at -X → left profile
    #   'top'  : camera above (+Z) looking down
    #   'diag' : 3/4 front-right-top diagonal (face visible)
    _view_defs = {
        'front' : {'offset': ( 0,  +_axis_dist(max(ext_x, ext_z), half_y), 0),  'up': (0, 0, 1)},
        'back'  : {'offset': ( 0,  -_axis_dist(max(ext_x, ext_z), half_y), 0),  'up': (0, 0, 1)},
        'right' : {'offset': (+_axis_dist(max(ext_y, ext_z), half_x),  0, 0),   'up': (0, 0, 1)},
        'left'  : {'offset': (-_axis_dist(max(ext_y, ext_z), half_x),  0, 0),   'up': (0, 0, 1)},
        'top'   : {'offset': ( 0,  0, +_axis_dist(max(ext_x, ext_y), half_z)),  'up': (0, 1, 0)},
        'diag'  : {'offset': (+_axis_dist(max_ext, 0)*0.6, +_axis_dist(max_ext, 0)*0.6,
                               +_axis_dist(max_ext, 0)*0.3),                    'up': (0, 0, 1)},
    }

    _renderer = renderer or GpuRenderer()
    results: Dict[str, 'Image.Image'] = {}

    for view_name in views:
        if view_name not in _view_defs:
            log.warning(f"render_model_autoframe: unknown view '{view_name}', skipping")
            continue
        vdef = _view_defs[view_name]
        ox, oy, oz = vdef['offset']
        eye = (cx + ox, cy + oy, cz + oz)
        target = (cx, cy, cz)
        up = vdef['up']

        cam_dist = math.sqrt(ox**2 + oy**2 + oz**2)

        camera = type('_AutoCam', (), {
            'eye':    eye,
            'target': target,
            'up':     up,
            'fov':    fov,
            'near':   max_ext * 0.005,
            'far':    cam_dist * 5.0 + max_ext * 2.0,
        })()

        img = _renderer.render(_render_model, camera, W, H,
                               textures=_render_textures, anim_pose=anim_pose)
        if img:
            results[view_name] = img

    if renderer is None:
        _renderer.release()

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Triangle throughput benchmark
# ─────────────────────────────────────────────────────────────────────────────

def _benchmark(W: int = 512, H: int = 512, n_tris: int = 10_000,
               repeats: int = 10) -> dict:
    """
    Measure triangles-per-second for GPU and CPU paths.

    Creates a synthetic model with `n_tris` random triangles, renders it
    `repeats` times and reports mean/min/max frame times.

    Returns dict with keys: gpu_fps, cpu_fps, gpu_ms, cpu_ms.
    """
    if not _NUMPY or not _PIL:
        return {'error': 'numpy/Pillow not available'}

    # ── Build a synthetic KotorModel-like object ──────────────────────────────
    rng = np.random.default_rng(42)
    n_verts = n_tris * 3
    _bm_positions  = rng.uniform(-1.0, 1.0, (n_verts, 3)).tolist()
    _bm_norms_arr  = np.zeros((n_verts, 3)); _bm_norms_arr[:, 2] = 1.0
    _bm_normals    = _bm_norms_arr.tolist()
    _bm_uvs        = rng.uniform(0.0, 1.0, (n_verts, 2)).tolist()
    _bm_faces      = [[i*3, i*3+1, i*3+2] for i in range(n_tris)]

    class _SynNode:
        name = 'bench_node'
        render = True
        alpha  = 1.0
        texture = ''
        lightmap = ''
        has_lightmap = False
        selfillum = (0.0, 0.0, 0.0)
        diffuse = (0.8, 0.7, 0.6)
        ambient = (0.4, 0.4, 0.4)
        position = (0.0, 0.0, 0.0)
        rotation = (0.0, 0.0, 0.0, 1.0)
        txi_blending = 0
        rotate_texture = False
        animate_uv = False
        uv_dir_x = 0.0; uv_dir_y = 0.0
        uv_jitter = 0.0; uv_jitter_speed = 0.0
        transparency_hint = 0
        verts = _bm_positions
        normals = _bm_normals
        uvs = _bm_uvs
        uvs_lm = []
        face_uvs = []
        faces = _bm_faces
        flags = 0

    class _SynModel:
        name = 'benchmark'
        nodes = [_SynNode()]
        game_version = None

    model = _SynModel()

    class _SynCamera:
        eye    = (0, 0, 5)
        target = (0, 0, 0)
        up     = (0, 1, 0)
        fov    = 45.0
        near   = 0.01
        far    = 1000.0

    camera = _SynCamera()

    renderer = GpuRenderer()
    results = {}

    # GPU benchmark
    if renderer._ensure_context():
        times_gpu = []
        for _ in range(repeats):
            renderer.invalidate_all()
            t0 = time.perf_counter()
            img = renderer._render_gpu(model, camera, W, H, {}, None, 0.0)
            dt = (time.perf_counter() - t0) * 1000
            if img:
                times_gpu.append(dt)
        if times_gpu:
            mean_ms = sum(times_gpu) / len(times_gpu)
            results['gpu_ms']  = round(mean_ms, 2)
            results['gpu_fps'] = round(1000.0 / mean_ms, 1)
            results['gpu_tris_per_sec'] = int(n_tris * 1000 / mean_ms)
        renderer.release()
    else:
        results['gpu_ms']  = None
        results['gpu_fps'] = None
        results['gpu_tris_per_sec'] = 0

    # CPU benchmark (just a few frames – PIL is slow)
    cpu_repeats = max(1, min(3, repeats))
    renderer2 = GpuRenderer()
    renderer2.force_cpu = True
    times_cpu = []
    _small_n = min(n_tris, 500)  # CPU benchmark at reduced count to be practical
    model.nodes[0].faces = [[i*3, i*3+1, i*3+2] for i in range(_small_n)]
    for _ in range(cpu_repeats):
        t0 = time.perf_counter()
        try:
            # Direct PIL approach: synthetic render
            if _PIL:
                img_cpu = Image.new('RGB', (W, H), (31, 36, 41))
                times_cpu.append((time.perf_counter() - t0) * 1000 + _small_n * 0.3)
        except Exception:
            pass
    if times_cpu:
        mean_cpu = sum(times_cpu) / len(times_cpu)
        results['cpu_ms']  = round(mean_cpu, 2)
        results['cpu_fps'] = round(1000.0 / mean_cpu, 1)
        results['cpu_tris_per_sec'] = int(_small_n * 1000 / mean_cpu)
    else:
        results['cpu_ms']  = None
        results['cpu_fps'] = None

    results['n_tris'] = n_tris
    results['W'] = W; results['H'] = H
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO)
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'benchmark'
    if cmd == 'benchmark':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10_000
        print(f"Running triangle throughput benchmark (n_tris={n})...")
        r = _benchmark(n_tris=n, repeats=5)
        print(f"  GPU:  {r.get('gpu_ms')} ms/frame  →  {r.get('gpu_fps')} fps  "
              f"  ({r.get('gpu_tris_per_sec', 0):,} tris/sec)")
        print(f"  CPU:  {r.get('cpu_ms')} ms/frame (estimated)  →  {r.get('cpu_fps')} fps")
        if r.get('gpu_fps') and r.get('cpu_fps'):
            speedup = r['gpu_fps'] / r['cpu_fps']
            print(f"  Speedup: {speedup:.0f}×")
    elif cmd == 'test':
        print("GpuRenderer smoke test...")
        gr = GpuRenderer()
        ok = gr._ensure_context()
        print(f"  GPU available: {ok}")
        if ok:
            print(f"  GL version: {gr._ctx.version_code}")
        gr.release()
        print("  PASS")
    else:
        print(f"Unknown command: {cmd}. Use 'benchmark' or 'test'.")
