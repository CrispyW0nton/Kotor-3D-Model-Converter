#version 300 es

layout (location = 0) in vec3 flags;
layout (location = 1) in vec3 position;
layout (location = 2) in vec3 normal;
layout (location = 3) in vec3 uv;
layout (location = 4) in vec3 uv2;

out vec2 diffuse_uv;
out vec2 lightmap_uv;
out vec4 pos;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

void main()
{
    gl_Position = projection * view * model * vec4(position, 1.0);
    diffuse_uv = vec2(uv.x, uv.y);
    lightmap_uv = vec2(uv2.x, uv2.y);
    pos = gl_Position;
}
