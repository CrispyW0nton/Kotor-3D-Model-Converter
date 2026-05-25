struct Locals {
    mvp: mat4x4<f32>,
    color: vec4<f32>,
    flags: vec4<f32>,
    params: vec4<f32>,
};

@group(0) @binding(0)
var<uniform> locals: Locals;

struct SceneLight {
    position_radius: vec4<f32>,
    direction_cone: vec4<f32>,
    color_intensity: vec4<f32>,
    flags: vec4<f32>,
};

struct LightingState {
    ambient_global: vec4<f32>,
    flags: vec4<f32>,
};

@group(0) @binding(1)
var<storage, read> scene_lights: array<SceneLight, 64>;

@group(0) @binding(2)
var<uniform> lighting_state: LightingState;

@group(1) @binding(0)
var diffuse_tex: texture_2d<f32>;
@group(1) @binding(1)
var diffuse_sampler: sampler;
@group(1) @binding(2)
var lightmap_tex: texture_2d<f32>;
@group(1) @binding(3)
var lightmap_sampler: sampler;

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) uv0: vec2<f32>,
    @location(3) uv1: vec2<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) normal: vec3<f32>,
    @location(1) uv0: vec2<f32>,
    @location(2) uv1: vec2<f32>,
    @location(3) world_position: vec3<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.position = locals.mvp * vec4<f32>(input.position, 1.0);
    out.normal = normalize(input.normal);
    out.world_position = input.position;
    // TextureCache supplies bottom-up RGBA images. KotOR UV V=0 is texture top,
    // so WGPU uses the same V flip as the established ModernGL path.
    out.uv0 = vec2<f32>(input.uv0.x, 1.0 - input.uv0.y);
    out.uv1 = vec2<f32>(input.uv1.x, 1.0 - input.uv1.y);
    return out;
}

fn scene_light_shade(normal: vec3<f32>, world_position: vec3<f32>) -> vec3<f32> {
    var accum = lighting_state.ambient_global.rgb * lighting_state.ambient_global.a;
    let max_count = min(u32(lighting_state.flags.x), 64u);
    for (var i = 0u; i < max_count; i = i + 1u) {
        let light = scene_lights[i];
        if (light.flags.x < 0.5) {
            continue;
        }
        let kind = i32(light.flags.y + 0.5);
        let color = light.color_intensity.rgb * light.color_intensity.a;
        if (kind == 4 || light.flags.z > 0.5) {
            accum = accum + color;
            continue;
        }
        var light_dir = vec3<f32>(0.0, 0.0, 1.0);
        var attenuation = 1.0;
        if (kind == 1) {
            light_dir = normalize(-light.direction_cone.xyz);
        } else {
            let delta = light.position_radius.xyz - world_position;
            let distance = length(delta);
            let radius = max(light.position_radius.w, 0.001);
            if (distance > radius) {
                continue;
            }
            light_dir = delta / max(distance, 0.0001);
            let falloff = clamp(1.0 - distance / radius, 0.0, 1.0);
            attenuation = falloff * falloff;
            if (kind == 3) {
                attenuation = mix(attenuation, falloff, clamp(light.flags.w * 0.25, 0.0, 0.6));
            }
            if (kind == 2) {
                let spot_dir = normalize(light.direction_cone.xyz);
                let cone = dot(normalize(world_position - light.position_radius.xyz), spot_dir);
                let cone_cos = light.direction_cone.w;
                let spot = smoothstep(cone_cos, min(1.0, cone_cos + 0.18), cone);
                attenuation = attenuation * spot;
            }
        }
        if (light.flags.z > 0.5) {
            accum = accum + color * attenuation;
        } else {
            let ndotl = max(dot(normal, light_dir), 0.0);
            accum = accum + color * ndotl * attenuation;
        }
    }
    return clamp(accum, vec3<f32>(0.0), vec3<f32>(2.0));
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let diffuse_sample = textureSample(diffuse_tex, diffuse_sampler, input.uv0);
    var sampled = diffuse_sample;
    if (locals.flags.x < 0.5) {
        sampled = vec4<f32>(1.0, 1.0, 1.0, 1.0);
    }
    var out_color = vec4<f32>(sampled.rgb * locals.color.rgb, sampled.a * locals.color.a);

    if (lighting_state.flags.y > 0.5) {
        let n = normalize(input.normal);
        out_color = vec4<f32>(out_color.rgb * scene_light_shade(n, input.world_position), out_color.a);
    } else if (locals.params.y > 1.5) {
        let n = normalize(input.normal);
        let light = normalize(vec3<f32>(0.45, 0.35, 0.82));
        let ndotl = max(dot(n, light), 0.0);
        let soft_shade = clamp(0.76 + ndotl * 0.24, 0.70, 1.0);
        out_color = vec4<f32>(out_color.rgb * soft_shade, 1.0);
    }

    if (locals.flags.y > 0.5) {
        let lightmap_sample = textureSample(lightmap_tex, lightmap_sampler, input.uv1);
        let lm_strength = clamp(locals.params.x, 0.0, 4.0);
        if (locals.params.z > 2.5) {
            out_color = vec4<f32>(lightmap_sample.rgb, out_color.a);
        } else if (locals.params.z > 0.5 && locals.params.z < 1.5) {
            out_color = vec4<f32>(out_color.rgb * lightmap_sample.rgb * lm_strength, out_color.a);
        } else {
            let baked = mix(vec3<f32>(1.0), lightmap_sample.rgb * 2.0, clamp(lm_strength, 0.0, 1.0));
            out_color = vec4<f32>(out_color.rgb * baked, out_color.a);
        }
    }

    if (locals.flags.z > 0.5 && locals.flags.z < 1.5 && out_color.a < locals.flags.w) {
        discard;
    }

    if (locals.params.w > 0.5) {
        out_color = vec4<f32>(mix(out_color.rgb, vec3<f32>(1.0, 0.78, 0.12), 0.45), out_color.a);
    }

    return out_color;
}
