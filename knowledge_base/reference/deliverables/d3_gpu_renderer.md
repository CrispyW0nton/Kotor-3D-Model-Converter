# Deliverable 3: GPU Renderer Foundation
# ========================================
# File: src/gui/gpu_renderer.py (new/existing), src/gui/viewport.py (toggle)
# Priority: HIGH | Effort: ~55 hours | Risk: HIGH (new subsystem)

## Problem Statement
The CPU-only PIL rasterizer uses painter's algorithm:
- O(n log n) triangle sorting per frame
- MAX_TRIS = 80,000 cap
- No true z-buffer (inner geometry visible through faces: eyes, teeth)
- High RAM usage from multiple cache layers
- Cannot exceed ~15 fps on complex models

## Required Fix (from dev brief)
Create a ModernGL-based GPU renderer with:
1. True depth buffer (z-test eliminates painter's algorithm artifacts)
2. VBO/VAO per mesh node
3. GLSL vertex + fragment shaders
4. Three-pass rendering (opaque -> alpha-test -> transparent)
5. Camera controls (orbit, pan, zoom)
6. Toggle between CPU and GPU in viewport

## Tasks (from roadmap spreadsheet)
| Task | Description | Hours | Files | Acceptance |
|------|------------|-------|-------|------------|
| T301 | Create ModernGL context | 6 | gpu_renderer.py | Context creates without error |
| T302 | VBO/VAO pipeline | 8 | gpu_renderer.py | Per-mesh VAO with pos/norm/uv |
| T303 | GLSL shaders | 8 | gpu_renderer.py | MVP transform + Blinn-Phong + texture |
| T304 | Depth testing | 4 | gpu_renderer.py | GL_DEPTH_TEST enabled; no see-through |
| T305 | Texture parameters | 6 | gpu_renderer.py | GL_REPEAT/CLAMP per TXI; mipmaps |
| T306 | 3-pass rendering | 8 | gpu_renderer.py | Opaque -> cutout -> transparent |
| T307 | Camera controls | 6 | gpu_renderer.py | Orbit, pan, zoom; matches CPU cam |
| T308 | Viewport toggle | 4 | viewport.py, main_window.py | UI switch CPU<->GPU |
| T309 | Skeleton overlay | 5 | gpu_renderer.py | Line-draw bones over mesh |

## Cross-Reference Repos to Study BEFORE Coding
1. **reone** (`src/libs/graphics/`): Full OpenGL KotOR renderer
   - `context.cpp`: GL context setup, state management
   - `shaders/`: GLSL vertex/fragment shaders for KotOR rendering
   - `mesh.cpp`: VBO/VAO creation from Aurora model data
2. **KotOR.js** (`src/`): WebGL renderer for KotOR
   - Scene rendering pipeline with multi-pass
   - Texture manager with wrap mode handling
3. **PyKotor** (for MDL data flow into renderer)

## Book Principles (MUST follow)

### Hayes Ch 4: VBO/VAO Setup
```python
# ModernGL pattern:
import moderngl
ctx = moderngl.create_standalone_context()

# Per-mesh VAO creation:
vbo_pos = ctx.buffer(position_data)      # float32, 3 components
vbo_norm = ctx.buffer(normal_data)        # float32, 3 components  
vbo_uv = ctx.buffer(uv_data)             # float32, 2 components
ibo = ctx.buffer(index_data)              # uint32 indices

vao = ctx.vertex_array(
    program,
    [
        (vbo_pos, '3f', 'in_position'),
        (vbo_norm, '3f', 'in_normal'),
        (vbo_uv, '2f', 'in_texcoord'),
    ],
    index_buffer=ibo
)
```

### Hayes Ch 4 + Ch 9: Shader Template
```glsl
// Vertex Shader
#version 330 core
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

in vec3 in_position;
in vec3 in_normal;
in vec2 in_texcoord;

out vec3 v_normal;
out vec2 v_texcoord;
out vec3 v_frag_pos;

void main() {
    vec4 world_pos = u_model * vec4(in_position, 1.0);
    gl_Position = u_projection * u_view * world_pos;
    v_frag_pos = world_pos.xyz;
    v_normal = mat3(transpose(inverse(u_model))) * in_normal;
    v_texcoord = in_texcoord;
}

// Fragment Shader
#version 330 core
uniform sampler2D u_texture;
uniform float u_alpha_test;  // -1.0 = disabled, 0.0-1.0 = threshold

in vec3 v_normal;
in vec2 v_texcoord;
in vec3 v_frag_pos;

out vec4 frag_color;

void main() {
    vec4 tex_color = texture(u_texture, v_texcoord);
    
    // Alpha test (for cutout pass)
    if (u_alpha_test >= 0.0 && tex_color.a < u_alpha_test)
        discard;
    
    // Blinn-Phong lighting
    vec3 light_dir = normalize(vec3(0.5, 1.0, 0.3));
    float diff = max(dot(normalize(v_normal), light_dir), 0.0);
    vec3 ambient = 0.3 * tex_color.rgb;
    vec3 diffuse = 0.7 * diff * tex_color.rgb;
    
    frag_color = vec4(ambient + diffuse, tex_color.a);
}
```

### Hayes Ch 13: Depth Buffer Setup
```python
# ModernGL depth testing:
ctx.enable(moderngl.DEPTH_TEST)

# FBO with depth attachment:
color_tex = ctx.texture((width, height), 4)
depth_tex = ctx.depth_texture((width, height))
fbo = ctx.framebuffer(color_attachments=[color_tex], depth_attachment=depth_tex)
```

### Gregory Ch 8: Render Loop Integration with Tkinter
```python
def render_frame(self):
    """Called by tkinter's after() scheduling."""
    self.fbo.use()
    self.ctx.clear(0.2, 0.2, 0.2, 1.0)
    
    # Pass 1: Opaque geometry (depth write ON, depth test ON)
    self.ctx.enable(moderngl.DEPTH_TEST)
    self.ctx.depth_func = '<='
    for mesh in self.opaque_meshes:
        mesh.render()
    
    # Pass 2: Alpha-tested cutouts (depth write ON, alpha test)
    self.program['u_alpha_test'].value = 0.5
    for mesh in self.cutout_meshes:
        mesh.render()
    
    # Pass 3: Transparent (depth write OFF, blend ON, back-to-front)
    self.ctx.enable(moderngl.BLEND)
    self.ctx.depth_mask = False
    for mesh in sorted(self.transparent_meshes, key=lambda m: -m.depth):
        mesh.render()
    self.ctx.depth_mask = True
    
    # Read pixels and display in tkinter
    pixels = self.fbo.read(components=4)
    # Convert to PIL Image and update tkinter canvas
```

## Three-Pass Rendering Detail
| Pass | Depth Write | Depth Test | Blend | Alpha Test | Sort Order |
|------|------------|------------|-------|------------|------------|
| 1: Opaque | ON | ON (<=) | OFF | OFF | Any (front-to-back optimal) |
| 2: Cutout | ON | ON (<=) | OFF | ON (>0.5) | Any |
| 3: Transparent | OFF | ON (<=) | ON (SrcAlpha, 1-SrcAlpha) | OFF | Back-to-front |
| 4: Skeleton overlay | OFF | OFF | ON | OFF | After all |

## Acceptance Criteria
1. No depth artifacts (eyes/teeth hidden behind faces)
2. Textures tile correctly on modules (GL_REPEAT)
3. Alpha-tested textures (hair, foliage) display correctly
4. Transparent textures blend properly
5. 60 fps on models with 100k+ triangles
6. Camera orbit/pan/zoom matches CPU renderer behavior
7. Toggle between CPU and GPU works without restart
8. Skeleton overlay draws bone lines correctly
