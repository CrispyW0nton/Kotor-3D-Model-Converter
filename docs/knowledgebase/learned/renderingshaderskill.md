# Rendering And Shader Skill

Use this skill for renderer backends, OpenGL/D3D-style pipelines, GPU resources,
buffers, shader inputs, lighting, shadows, framebuffers, post-processing, and
shader debugging.

## Book Grounding

- `Computer_Graphics_Development_with_OpenGL_-_Wilson_Hayes.pdf`: graphics
  pipeline stages, VBO/VAO concepts, model-view-projection transforms,
  lighting/shading, textures, GLSL, real-time rendering, model loading,
  framebuffers, instancing, geometry/tessellation stages, and shadow mapping.
- `The_Book_of_Shaders_-_Patricio_Gonzalez_Vivo_and_Jen_Lowe.pdf`: fragment
  shaders, uniforms, `gl_FragCoord`, shaping functions, HSB/color mixing,
  distance fields, 2D matrices, procedural randomness/noise, textures, blending,
  and convolution filters.
- `Fundamentals_of_Computer_Graphics_-_Marschner_SteveShirley_Peter.pdf`:
  raster images, ray tracing, surface shading, transformation matrices, viewing,
  rasterization, antialiasing, culling, signal processing, and texture/filter
  reasoning.

## Workflow

1. Split the rendering issue into CPU asset truth, transformed scene data, GPU
   resource state, shader inputs, draw submission, raster/post-process output,
   and presentation.
2. Validate buffer layout and shader layout together: vertex stride, attribute
   order, index type, matrix convention, color space, normals/tangents, UVs,
   material IDs, and skin palette bindings.
3. Treat model-view-projection, normal transforms, and handedness as contract
   points. Name the space for every shader input.
4. For textures, verify decode, dimensions, format, color space, sampler state,
   UVs, mip/filter state, and backend upload separately.
5. For lighting/shadows, separate material response, light data, depth/shadow
   pass state, bias/precision, culling mode, and final composition.
6. For post-processing, verify framebuffer size, attachment format, render pass
   ordering, texture feedback hazards, and viewport/scissor state.
7. Add debug views when possible: normals, UVs, depth, material slots, lightmaps,
   shadow maps, draw IDs, and resource residency.

## Pipeline Checklist

- CPU input: mesh vertices/indices, material slots, textures, lightmaps, bones,
  weights, transforms, and scene object identity.
- Upload/resource state: buffer size, stride, usage flags, lifetime, cache key,
  dirty range, texture format, mip policy, and transition state.
- Vertex stage: attribute binding, index format, model/view/projection order,
  skinning palette, normal/tangent transform, handedness, and culling.
- Raster stage: viewport, scissor, depth test/write, face winding, blending,
  multisample/antialiasing, and clip-space conventions.
- Fragment/pixel stage: material uniforms, texture samplers, light data, color
  space, alpha policy, and fallback textures.
- Post-process: framebuffer size, attachment format, pass order, texture
  feedback hazards, and final presentation/swap-chain readiness.

## Shader Debugging Patterns

- Output constants first to prove the pass runs.
- Output UVs, normals, depth, material ID, or bone weight heatmaps to isolate
  bad inputs.
- For normal mapping, check tangent basis orientation before tuning lighting.
- For shadows, debug the depth map separately from the lit pass; bias fixes
  acne/peter-panning only after projection, culling, and depth formats are
  correct.
- For procedural/noise shaders, expose seed, frequency, amplitude, and domain
  transform as inspectable parameters.
- For image filters/convolution, verify kernel normalization, edge handling, and
  render-target color format before judging the visual result.

## GhostRigger Applications

- D3D12/ModernGL/PyGFX/native renderer parity.
- MDL mesh/material/texture/lightmap display.
- Module renderer fixture `K2:001ebo1` / `001EBO1`.
- Skinning palette, skeleton overlay, and animation pose debugging.
- Viewport selection overlays, gizmo rendering, and measurement drawing.
- Shader-like effects or procedural viewport overlays.

## Validation

- Use MCP only to confirm backend asset truth for MDL/material/texture data.
- Use visible Debug app testing for renderer output.
- For blank/black frames, check clear/present readiness, framebuffer attachment,
  resource binding, shader compile/link, viewport size, draw count, and culling.
- For wrong colors, check color space, texture decode, material slot, lightmap,
  shader uniform, and blending state.
- For animated mesh artifacts, check CPU pose truth, skin palette upload,
  attribute layout, weight normalization, and object-scoped pose selection.
