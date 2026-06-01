"""
gpu_renderer.py  Ã¢â‚¬â€œ  GhostRigger-K1-K2  GPU fast-path renderer
==============================================================
ModernGL/EGL GPU renderer for the Qt viewport.

Architecture
------------
GpuRenderer.render(model, camera, W, H) Ã¢â€ â€™ PIL Image (RGBA)

GPU fast-path  (requires moderngl + EGL)
  Ã¢â‚¬Â¢ Uploads all mesh vertex/UV data as interleaved VBOs (float32)
  Ã¢â‚¬Â¢ One draw-call per material zone (tex + lightmap + blend-mode)
  Ã¢â‚¬Â¢ Textures cached as GL Texture2D objects (RGBA8, mipmapped)
  Ã¢â‚¬Â¢ Supports:
      Ã¢â‚¬â€œ Diffuse UV mapping (UV0) with GL_REPEAT wrapping
      Ã¢â‚¬â€œ Lightmap compositing (UV1, overbright Ãƒâ€”2 multiply pass)
      Ã¢â‚¬â€œ TXI additive blending (GL_ONE + GL_ONE)
      Ã¢â‚¬â€œ TXI punch-through alpha (alpha-test discard at threshold)
      Ã¢â‚¬â€œ TXI environment map (unit 2): KotOR BlendedOver Ã¢â‚¬â€ env additive on
          top of diffuse, weighted by (1 - diffuse.alpha). Both envmaptexture
          and bumpyshinytexture TXI keywords map to this env-map slot.
      Ã¢â‚¬â€œ TXI specularcolour map (unit 3, Phase 3.8): per-texel gloss mask
          modulates Phong specular highlight intensity per fragment.
      Ã¢â‚¬â€œ RotateTexture (UV swap in vertex shader)
      Ã¢â‚¬â€œ UV scroll / animate_uv (uniform offset per draw)
      Ã¢â‚¬â€œ Self-illumination colour additive term in fragment shader
      Ã¢â‚¬â€œ Animated alpha (uniform)
      Ã¢â‚¬â€œ Per-node diffuse colour + Phong lighting (key + fill + ambient)
      Ã¢â‚¬â€œ Per-node shininess from ModelNode.shininess (Phase 3.8)

Key rendering correctness fixes (Phase 1)
  BUG-UV:   UV V-axis flipped  Ã¢â€ â€™ v_uv.y = 1.0 - in_uv.y  in vertex shader
             KotOR MDX stores V=0 at top (D3D convention); OpenGL wants V=0 at bottom.
  BUG-WIND: KotOR uses clockwise triangle winding; set ctx.front_face = 'cw'.
  BUG-ALPHA: Transparent surfaces sorted back-to-front by camera depth before draw.
  BUG-ENVMAP: TXI envmaptexture/bumpyshinytexture Ã¢â€ â€™ KotOR uses "BlendedOver"
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
                dict, bind a neutral grey 1Ãƒâ€”1 fallback instead of nothing.  This keeps
                the surface visible (correct) rather than fully transparent.
                The grey env contributes (1-diffuse.alpha)Ãƒâ€”grey to lit_color.
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
                fire) now advance the frame via anim_time Ãƒâ€” txi_fps and pass a UV tile
                offset uniform (u_flipbook_offset) to the vertex shader.
                Reference: KotOR TXI spec proceduretype/numx/numy/fps.
  FIX-PERSCACHE: Per-model persistent world-transform cache survives across frames;
                invalidated on model change.  Reduces O(NÃƒâ€”depth) per-frame cost to
                O(1) cache lookup for static geometry.

Vertex-space contract (Phase D20-M Ã¢â‚¬â€ SUPERSEDES the old BUG-SKIN note)
  Every node carries a ``vertex_space`` enum set at load time by
  ``src/core/vertex_space.compute_vertex_space()``.  ``_build_vbo_data`` reads
  that field and nothing else to decide whether to transform vertices:

      NODE_LOCAL (0): vertices are node-local; apply full parent-chain
                      world_transform (rotate + translate).  This is the
                      DEFAULT for every KotOR MDL node Ã¢â‚¬â€ including SKIN,
                      DANGLY, and SABER.  Skin meshes are node-local per
                      xoreos ``model_kotor.cpp`` readSkin() and KotOR.js
                      ``OdysseyModelNodeMesh.ts``.  The pre-D20-M claim
                      that skin vertices were "already in world-space and
                      baked by the NWN exporter" was WRONG Ã¢â‚¬â€ it was a
                      coincidence on models whose skin parent chain happened
                      to resolve to identity.
      WORLD (1):      vertices already in model-root space (only set for
                      externally-imported OBJ/FBX); skip world_transform.
                      Not produced by any KotOR MDL loader path.
      AABB_WALK (2):  walkmesh / collision Ã¢â‚¬â€ never rendered.

  See ``_build_vbo_data`` (the ``_node_vs`` switch) and ``src/core/vertex_space.py``
  for the authoritative implementation.  Do NOT reintroduce centroid-magnitude
  or name-based heuristics to decide vertex space Ã¢â‚¬â€ the enum is the contract.

Phase 3.8 rendering correctness fixes (deep audit vs Kotor.NET / KotOR.js / xoreos)
  FIX-ENVBLEND:  CRITICAL: The environment-map blend weight was inverted.
                 Old (wrong): env_weight = diffuse.a   Ã¢â€ â€™ env replaces opaque areas
                 New (correct): env_weight = 1.0 - diffuse.a  Ã¢â€ â€™ env shows through
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
  FIX-ENVOPAQUE: After env-map blend, diffuse.a is set to 1.0 Ã¢â‚¬â€ prevents the already-
                 consumed alpha from accidentally making env-map surfaces transparent.
  FIX-LMSHADE:  For module/area geometry with baked lightmaps, skip the Phong
                 directional lighting pass entirely.  The lightmap IS the lighting
                 Ã¢â‚¬â€ applying Phong shade on top double-darkens the scene because
                 lightmaps have a mean intensity of ~0.25 (Ãƒâ€”2 overbright Ã¢â€ â€™ ~0.5)
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
                the global default 20.0.  Zero shininess Ã¢â€ â€™ no specular highlight.
  FIX-MULTILAYER: build_creature_model() now accepts an optional 'accessory_resrefs'
                list; each accessory MDL is loaded and attached as an overlay model
                by merging its non-skin geometry nodes into a combined scene list.
                This enables cloak/robe/headgear layering over the base body model.
                Sources: KotOR.js OdysseyModel3D.ts:780Ã¢â‚¬â€œ803 supermodel stacking;
                Kotor.NET CompositeModel multi-mesh logic.

CPU graphics rendering
  Ã¢â‚¬Â¢ Disabled. The Qt viewport and renderer failure paths do not rasterize on CPU.

Performance notes
  Ã¢â‚¬â€œ GPU path: ~1 ms/frame for typical 10 k-tri KotOR models
  Ã¢â‚¬â€œ CPU path: ~300 ms/frame for same (PIL AFFINE per triangle)
  Ã¢â‚¬â€œ The GPU path is ~300Ãƒâ€” faster for fully textured rendering.

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

from src.adapters.gpu.moderngl_context import (
    _create_moderngl_standalone_context,
    _gl_context_backend_candidates,
)
from src.adapters.gpu.moderngl_runtime import *  # noqa: F401,F403
from src.core.lighting.light_gizmo_renderer import (
    LIGHT_HELPER_AREA_SIZE,
    LIGHT_HELPER_COLORS,
    LIGHT_HELPER_DIRECTION_LENGTH,
    LIGHT_HELPER_MARKER_RADIUS,
    LIGHT_HELPER_POINT_RADIUS,
    LIGHT_HELPER_SELECTED_BOOST,
    LIGHT_HELPER_SPOT_CAP_MAX_RADIUS,
    LIGHT_HELPER_SPOT_LENGTH,
)
from src.core.rendering.gpu_diagnostics_config import *  # noqa: F401,F403
from src.core.rendering.gpu_diagnostics_records import *  # noqa: F401,F403
from src.core.rendering.color_utils import *  # noqa: F401,F403

from src.adapters.gpu.viewport_probe import *  # noqa: F401,F403
from src.core.geometry.model_data import KOTOR_BASE_SKELETONS as _KOTOR_BASE_SKELETONS
from src.core.rendering.gpu_debug_tables import ModuleDrawItem
from src.core.special.render_constants import (
    FACE_MESH_SUBSTRINGS as _FACE_MESH_SUBSTRINGS,
    INNER_GEO_SUBSTRINGS as _INNER_GEO_SUBSTRINGS,
)

__all__ = tuple(name for name in globals() if not name.startswith("__"))
