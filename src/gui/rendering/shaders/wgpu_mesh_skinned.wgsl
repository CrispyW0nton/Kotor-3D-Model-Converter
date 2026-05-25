struct Locals {
    mvp: mat4x4<f32>,
    color: vec4<f32>,
    flags: vec4<f32>,
    params: vec4<f32>,
};

@group(0) @binding(0)
var<uniform> locals: Locals;

@group(1) @binding(0)
var diffuse_tex: texture_2d<f32>;
@group(1) @binding(1)
var diffuse_sampler: sampler;
@group(1) @binding(2)
var lightmap_tex: texture_2d<f32>;
@group(1) @binding(3)
var lightmap_sampler: sampler;

@group(2) @binding(0)
var<storage, read> bone_palette: array<mat4x4<f32>>;

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) uv0: vec2<f32>,
    @location(3) uv1: vec2<f32>,
    @location(4) bone_indices: vec4<u32>,
    @location(5) bone_weights: vec4<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) normal: vec3<f32>,
    @location(1) uv0: vec2<f32>,
    @location(2) uv1: vec2<f32>,
};

fn skin_position(input: VertexInput) -> vec4<f32> {
    let p = vec4<f32>(input.position, 1.0);
    var out = vec4<f32>(0.0, 0.0, 0.0, 0.0);
    out = out + (bone_palette[input.bone_indices.x] * p) * input.bone_weights.x;
    out = out + (bone_palette[input.bone_indices.y] * p) * input.bone_weights.y;
    out = out + (bone_palette[input.bone_indices.z] * p) * input.bone_weights.z;
    out = out + (bone_palette[input.bone_indices.w] * p) * input.bone_weights.w;
    return vec4<f32>(out.xyz, 1.0);
}

fn skin_normal(input: VertexInput) -> vec3<f32> {
    let n = input.normal;
    var out = vec3<f32>(0.0, 0.0, 0.0);
    out = out + (bone_palette[input.bone_indices.x] * vec4<f32>(n, 0.0)).xyz * input.bone_weights.x;
    out = out + (bone_palette[input.bone_indices.y] * vec4<f32>(n, 0.0)).xyz * input.bone_weights.y;
    out = out + (bone_palette[input.bone_indices.z] * vec4<f32>(n, 0.0)).xyz * input.bone_weights.z;
    out = out + (bone_palette[input.bone_indices.w] * vec4<f32>(n, 0.0)).xyz * input.bone_weights.w;
    return normalize(out);
}

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    let skinned_position = skin_position(input);
    out.position = locals.mvp * skinned_position;
    out.normal = skin_normal(input);
    out.uv0 = vec2<f32>(input.uv0.x, 1.0 - input.uv0.y);
    out.uv1 = vec2<f32>(input.uv1.x, 1.0 - input.uv1.y);
    return out;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let diffuse_sample = textureSample(diffuse_tex, diffuse_sampler, input.uv0);
    var sampled = diffuse_sample;
    if (locals.flags.x < 0.5) {
        sampled = vec4<f32>(1.0, 1.0, 1.0, 1.0);
    }
    var out_color = vec4<f32>(sampled.rgb * locals.color.rgb, sampled.a * locals.color.a);

    if (locals.params.y > 1.5) {
        let n = normalize(input.normal);
        let light = normalize(vec3<f32>(0.45, 0.35, 0.82));
        let ndotl = max(dot(n, light), 0.0);
        out_color = vec4<f32>(out_color.rgb * (0.45 + ndotl * 0.55), out_color.a);
    }

    if (locals.flags.y > 0.5) {
        let lightmap_sample = textureSample(lightmap_tex, lightmap_sampler, input.uv1);
        out_color = vec4<f32>(
            out_color.rgb * lightmap_sample.rgb * locals.params.x,
            out_color.a
        );
    }

    if (locals.flags.z > 0.5 && locals.flags.z < 1.5 && out_color.a < locals.flags.w) {
        discard;
    }

    return out_color;
}
