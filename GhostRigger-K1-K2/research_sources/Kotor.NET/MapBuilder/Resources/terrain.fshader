#version 300 es
precision highp float;

in vec2 diffuse_uv;
in vec2 lightmap_uv;
in vec3 worldSpacePosition;

out vec4 FragColor;

uniform sampler2D diffuse;
uniform sampler2D lightmap;
uniform int enableLightmap;
uniform vec3 mousePosition;

void main()
{
    vec2 mousePosition2D = vec2(mousePosition);
    vec2 vertexPosition2D = vec2(worldSpacePosition);
    float strengthAtVertex = 0.0;

    vec4 diffuseColor = texture(diffuse, diffuse_uv);
    vec4 whiteColor = vec4(1, 1, 1, 1);

    float brushSize = 5.0f;

    // This will return a range from 0.0 - 1.0, from the edge of the brush to the centre of the brush.
    float distanceFromMouseToVertex = (brushSize - distance(mousePosition2D, vertexPosition2D)) / brushSize;
    float distanceFromMouseToVertexBounded = clamp(distanceFromMouseToVertex, 0.0f, 1.0f);

    // Linear brush
    strengthAtVertex = distanceFromMouseToVertexBounded;

    // Sharp brush
    //strengthAtVertex = pow(distanceFromMouseToVertexBounded, 2.0f);
    
    // Sphere brush
    //strengthAtVertex = log2(distanceFromMouseToVertexBounded + 1.0f);

    // Constant brush
    if (distanceFromMouseToVertexBounded > 0) strengthAtVertex = 1.0f;     

    // Smooth brush
    //float x = distanceFromMouseToVertexBounded;
    //strengthAtVertex = ((2 * x) + 0.7*(2x-1)) / (-0.7 - 2*-0.7*abs(2*x - 1) + 1) + 1;


    FragColor = mix(diffuseColor, whiteColor, strengthAtVertex);
}
