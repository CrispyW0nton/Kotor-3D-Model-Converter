#version 300 es

layout (location = 0) in vec3 flags;
layout (location = 1) in vec3 position;
layout (location = 2) in vec3 normal;
layout (location = 3) in vec3 uv;
layout (location = 4) in vec3 uv2;

void main()
{
    gl_Position = vec4(position, 1.0);
}
