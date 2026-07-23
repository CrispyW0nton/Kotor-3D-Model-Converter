from __future__ import annotations

_VERT_SRC = """
#version 330 core

// Per-vertex inputs
in vec3  in_pos;       // model/world position from _build_vbo_data; scene placement uses u_model
in vec3  in_norm;      // matching normal basis for in_pos
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
    // Ordinary MDL draws already provide world-space normals; scene-object
    // placement uses u_normal_mat so rotate/scale stay on the GPU.
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
uniform int   u_scene_lighting; // 0 unlit, 1 studio, 2 Aurora scene lights, 3 baked-lightmap preview
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

// Map Studio routes the measured ARE distance-fog values through these
// uniforms only for its authored-preview model.  They default off for every
// model/particle view, preserving existing retail rendering byte-for-byte.
uniform int   u_map_fog_enabled;
uniform vec3  u_map_fog_color;
uniform float u_map_fog_near;
uniform float u_map_fog_far;

// v7.2 Order-Independent Transparency (Finding 5.5 — reone f_oit_model.glsl)
uniform int   u_oit_enabled;    // 1 = weighted-blended OIT output mode
uniform int   u_debug_visualize; // 0 normal, 1 red, 2 alpha, 3 diffuse, 4 lightmap
uniform int   u_lm_composite_mode; // 0 current, 1 multiply, 2 overbright2, 3 clamp diagnostic
uniform int   u_wireframe_enabled;
uniform vec3  u_wire_color;
uniform int   u_render_mode; // 0 realistic, 1 flat, 2 shaded
uniform int   u_selected;
uniform float u_sprite_alpha_source; // 1 = derive alpha from sprite luminance/black matte
uniform float u_sprite_glow;         // emissive sprite boost from Sprite Materials panel

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
        } else if (kind == 4) {
            // Ambient lights are global energy, not local point emitters.
            attenuation = 1.0;
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

        if (u_scene_light_ambient_only[i] == 1 || kind == 4) {
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

vec3 spriteEmissionTint(vec3 color) {
    float peak = max(max(color.r, color.g), color.b);
    if (peak <= 0.001) {
        return color;
    }
    return mix(color, color / peak, 0.35);
}

float spriteKeyedAlpha(vec4 sampled) {
    float peak = max(max(sampled.r, sampled.g), sampled.b);
    float keyed_alpha = smoothstep(0.08, 0.40, peak);
    return sampled.a < 0.999 ? min(sampled.a, keyed_alpha) : keyed_alpha;
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
    bool sprite_emissive = u_sprite_alpha_source > 0.5 && u_sprite_glow > 0.001;
    if (u_sprite_alpha_source > 0.5) {
        diffuse_samp.a = spriteKeyedAlpha(diffuse_samp);
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
        // Preserve the user-facing intensity blend, but restore the validated
        // pre-lighting-system KotOR preview target.  The May lightmap audit
        // used 2.5x overbright plus a 0.03 floor; the later generic-lighting
        // rewrite accidentally replaced that target with 2.0x and no floor.
        vec3 baked_target = lm_samp.rgb * 2.5 + vec3(0.03);
        vec3 baked_light = mix(vec3(1.0), baked_target, clamp(lm_strength, 0.0, 1.0));
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
            // FIX-LMBRIGHT: 2.5x overbright + 0.03 ambient floor.
            lit_color = diffuse_samp.rgb * baked_light;
            if (u_lm_composite_mode == 3) {
                lit_color = clamp(lit_color, 0.0, 1.0);
            }
        }

        // Odyssey self-illumination is a lighting contribution that is still
        // modulated by the diffuse texture.  Adding the controller RGB as a
        // flat colour destroys dark texture detail (DOR_LKO04 becomes an
        // opaque white panel).  reone's retro shader computes
        // ``(lighting + selfIllum) * mainTex`` and KotOR.js applies the same
        // texture-preserving contract.
        lit_color += diffuse_samp.rgb * u_selfillum;

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
        if (sprite_emissive) {
            lit_color = diffuse_samp.rgb;
        } else if (u_scene_lighting == 2 && u_scene_light_count > 0) {
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

        // -- Self-illumination (texture-modulated lighting contribution)
        // Preserve the albedo/atlas contours while raising their emitted
        // light.  A flat RGB add turns high selfillum stock doors and props
        // into featureless white silhouettes.
        lit_color += diffuse_samp.rgb * u_selfillum;

        // -- Lightmap compositing for non-lm_shade path (fallback):
        // This handles lightmapped nodes that somehow reach this path
        // (e.g. character models with lightmap textures).
        if (u_has_lm == 1) {
            vec4 lm_samp = texture(u_lm_tex, v_uv_lm);
            debug_lightmap_rgb = lm_samp.rgb;
            float lm_strength = clamp(u_lightmap_intensity, 0.0, 4.0);
            vec3 baked_target = lm_samp.rgb * 2.5 + vec3(0.03);
            vec3 baked_light = mix(vec3(1.0), baked_target, clamp(lm_strength, 0.0, 1.0));
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
        float selfillum_peak = max(u_selfillum.r, max(u_selfillum.g, u_selfillum.b));
        lit_color = selfillum_peak > 0.0001
            ? diffuse_samp.rgb * max(vec3(0.25), u_selfillum)
            : diffuse_samp.rgb;
    }

    if (u_render_mode == 1) {
        lit_color = diffuse_samp.rgb;
    } else if (u_render_mode == 2) {
        float soft_shade = clamp(0.76 + max(dot(N, u_light_dir), 0.0) * 0.24, 0.70, 1.0);
        lit_color = diffuse_samp.rgb * soft_shade;
        diffuse_samp.a = 1.0;
    }

    // The blade mask is already an emissive RGB texture.  Preserve its black
    // card edges and colored falloff exactly; adding u_selfillum would turn the
    // whole additive quad into a visible rectangle.
    if (featureEnabled(u_features, FEAT_SABER)) {
        lit_color = diffuse_samp.rgb;
    }

    // TXI 'blending additive' surfaces are unlit emissive textures in the
    // Odyssey engine (reone/xoreos draw them fullbright).  Phong shading plus
    // the flat u_selfillum term pushes overlapping additive shells (e.g. the
    // K1 Star Map SkyDome pair) to solid white under ONE,ONE blending.
    // Untextured additive planes (texture 'null' + selfillum, e.g. the Star
    // Map lightflare burst) glow with their selfillum color instead of the
    // white fallback texture.
    if (u_blend_mode == 1 && !sprite_emissive) {
        lit_color = diffuse_samp.rgb;
        if (u_has_tex == 0) {
            lit_color = diffuse_samp.rgb * u_selfillum;
        }
    }

    if (u_selected == 1) {
        lit_color = mix(lit_color, vec3(1.0, 0.78, 0.12), 0.45);
    }

    if (sprite_emissive && u_render_mode == 0) {
        vec3 tint = spriteEmissionTint(diffuse_samp.rgb);
        vec3 emission = max(diffuse_samp.rgb, tint * (0.45 + diffuse_samp.a * 0.55));
        lit_color = max(lit_color, emission * (1.0 + clamp(u_sprite_glow, 0.0, 4.0)));
    }

    // K1 exterior SunFog uses camera distance.  Never apply this to additive
    // effects or sprite-emissive particles: those retain their established
    // renderer path, and the state is opt-in for a Map Studio world preview.
    // Map Studio feeds a compact-view calibrated range here; the authored ARE
    // range remains untouched for package export and real-game rendering.
    if (u_map_fog_enabled == 1 && u_blend_mode != 1 && !sprite_emissive) {
        float fog_range = max(0.001, u_map_fog_far - u_map_fog_near);
        float fog_linear = clamp((length(v_world_pos - u_cam_pos) - u_map_fog_near) / fog_range, 0.0, 1.0);
        // A slightly front-loaded atmospheric ramp makes the state readable
        // inside author-sized clearings instead of requiring a 70 m sightline.
        float fog_amount = 1.0 - exp(-2.15 * fog_linear);
        fog_amount = fog_amount * fog_amount * (3.0 - 2.0 * fog_amount);
        lit_color = mix(lit_color, u_map_fog_color, fog_amount);
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
    } else if (u_blend_mode == 1) {
        // Additive blending is ONE,ONE: destination ignores alpha entirely, so
        // node-alpha fades (Star Map SkyDome off/on animation) must premultiply
        // into the added color or additive surfaces can never fade out.
        frag_color = vec4(lit_color * final_alpha, final_alpha);
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


__all__ = tuple(name for name in globals() if not name.startswith("__"))
