# GhostRigger Cross-Reference Map
# ================================
# Maps every GhostRigger feature to: source files, reference repos, and book sections.
# CONSULT THIS before implementing any feature to avoid hallucinating solutions.

---

## Feature Cross-Reference Matrix

### 1. MDL Binary Parsing
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Binary header | `src/core/model_data.py` | PyKotor: `resource/formats/mdl/io_mdl.py` | - |
| Node hierarchy | `src/core/model_data.py` | KotorBlender: `io_scene_kotor/scene/modelnode/trimesh.py` | Mukundan 7.3 |
| Geometry data | `src/core/model_data.py` | xoreos: `src/graphics/aurora/model_kotor.cpp` | Mukundan 2.1 |
| MDX companion | `src/core/model_data.py` | PyKotor: `resource/formats/mdl/io_mdl.py` | - |

### 2. Skeleton & Joint Hierarchy
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Joint tree | `src/core/model_data.py` | KotorBlender: `io_scene_kotor/scene/modelnode/aabb.py` | Mukundan 7.3 |
| Local transforms | `src/core/model_data.py` | PyKotor: `resource/generics/mdl.py` | Gregory 5.3 |
| Quaternion orient. | `src/core/model_data.py` | reone: `src/libs/graphics/model.cpp` | Gregory 5.4 |
| Supermodel ref | `src/core/model_data.py` | KotOR.js: `resource/mdl/AuroraModel.ts` | - |

### 3. Skin Weights & Bone Binding
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Weight arrays | `src/core/model_data.py` | PyKotor: `resource/formats/mdl/io_mdl.py` (skin node) | Mukundan 7.6 |
| Bone indices | `src/core/model_data.py` | KotorBlender: `io_scene_kotor/scene/modelnode/skin.py` | Mukundan 7.5 |
| Weight normalize | `src/converters/mesh_converter.py` | ufbx: `ufbx.h` (ufbx_skin_cluster) | Mukundan 7.6 |
| Max influences | `src/converters/mesh_converter.py` | ufbx: `ufbx.h` | Mukundan 7.6 |

### 4. FBX Export (Deliverable 1)
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| ASCII structure | `src/converters/mesh_converter.py` | ufbx: `test/` (reference FBX files) | - |
| Bone hierarchy | `src/converters/mesh_converter.py` | KotorBlender: `io_scene_kotor/format/mdl/exporter.py` | Mukundan 7.5 |
| Skin deformer | `src/converters/mesh_converter.py` | ufbx: `ufbx.h` (ufbx_skin_deformer) | Mukundan 7.5-7.6 |
| Bind-pose matrix | `src/converters/mesh_converter.py` | FBX2glTF: `src/fbx/` | Mukundan 7.5.1, Gregory 5.3 |
| Weight export | `src/converters/mesh_converter.py` | ufbx: `ufbx.h` | Mukundan 7.6 |
| Unreal compat. | `src/converters/mesh_converter.py` | FBX2glTF (validation patterns) | - |

### 5. OBJ Export
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Vertex/face fmt | `src/converters/mesh_converter.py` | - | Mukundan 2.2 (Box 2.1) |
| Normal export | `src/converters/mesh_converter.py` | - | Mukundan 2.7 |
| UV export | `src/converters/mesh_converter.py` | - | Mukundan 2.2 |

### 6. glTF/GLB Export
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Buffer layout | `src/converters/mesh_converter.py` | FBX2glTF: `src/gltf/` | - |
| Skin extension | `src/converters/mesh_converter.py` | FBX2glTF | Mukundan 7.5-7.6 |
| Animation | `src/converters/mesh_converter.py` | KotOR.js: `resource/mdl/` | Mukundan 7.4 |

### 7. Texture Loading (TPC/TGA)
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| TPC decode | `src/core/model_data.py` | PyKotor: `resource/formats/tpc/io_tpc.py` | - |
| TXI metadata | `src/core/model_data.py` | KotOR.js: `resource/tpc/TPCObject.ts` | Hayes Ch 7 |
| DXT decompress | `src/core/model_data.py` | reone: `src/libs/graphics/texture.cpp` | - |

### 8. UV / Texture Wrapping (Deliverable 2)
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| UV sentinel | `src/gui/viewport.py` | NONE (GhostRigger-specific hack) | Hayes Ch 7 |
| GL_REPEAT | `src/gui/gpu_renderer.py` | KotOR.js: `resource/tpc/TPCObject.ts` | Hayes Ch 7 |
| TXI clamp | `src/gui/viewport.py` | KotOR.js: `resource/tpc/TPCObject.ts` | Hayes Ch 7 |
| frac() in shader | `src/gui/gpu_renderer.py` | reone: `src/libs/graphics/shaders/` | Hayes Ch 7 |

### 9. CPU Renderer (PIL/Painter's Algorithm)
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Triangle sort | `src/gui/viewport.py` | NONE | - |
| Rasterization | `src/gui/viewport.py`, `src/gui/accel.py` | NONE | - |
| Alpha test | `src/gui/viewport.py` | NONE | Hayes Ch 7 |

### 10. GPU Renderer (Deliverable 3)
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| ModernGL ctx | `src/gui/gpu_renderer.py` | reone: `src/libs/graphics/context.cpp` | Hayes Ch 4 |
| VBO/VAO setup | `src/gui/gpu_renderer.py` | KotOR.js: `resource/mdl/AuroraModel.ts` | Hayes Ch 4 |
| Vertex shader | `src/gui/gpu_renderer.py` | reone: `src/libs/graphics/shaders/` | Hayes Ch 4, Ch 9 |
| Fragment shader | `src/gui/gpu_renderer.py` | reone: `src/libs/graphics/shaders/` | Hayes Ch 7, Ch 9 |
| Depth testing | `src/gui/gpu_renderer.py` | reone: `src/libs/graphics/context.cpp` | Hayes Ch 13 |
| 3-pass render | `src/gui/gpu_renderer.py` | KotOR.js (render pipeline) | Hayes Ch 9 |
| MSAA | `src/gui/gpu_renderer.py` | - | Hayes Ch 13 |
| Camera controls | `src/gui/gpu_renderer.py` | KotOR.js: `controls/` | Gregory 8.1 |

### 11. Animation Engine
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Keyframe interp | `src/core/animation_engine.py` | KotOR.js: `resource/mdl/AuroraAnimation.ts` | Mukundan 7.4, 7.5.3 |
| SLERP | `src/core/animation_engine.py` | PyKotor: quaternion utils | Gregory 5.4, Mukundan 7.5.3 |
| Supermodel anim | `src/core/animation_engine.py` | KotorBlender: animation handling | - |
| Retargeting | `src/core/animation_engine.py` | - | Mukundan 7.7 |

### 12. Character Builder (Deliverable 4)
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Workspace UI | `src/gui/character_builder_window.py` | - | - |
| Part library | `src/gui/character_builder_window.py` | PyKotor: resource enumeration | Gregory 7.2 |
| Head hook snap | `src/gui/character_builder_window.py` | KotorBlender: head/body hooks | - |
| Rig transfer | `src/autorig/auto_rigger.py` | KotorBlender: armature transfer | Mukundan 7.7 |
| Weight painting | `src/gui/character_builder_window.py` | - | Mukundan 7.6 |
| Validation | `src/gui/character_builder_window.py` | - | - |

### 13. Resource Management (Deliverable 5)
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Lazy loading | `src/resources/resource_manager.py` | - | Gregory 7.2 |
| Cache eviction | `src/resources/resource_manager.py` | - | Gregory 7.2 |
| Memory budget | `src/resources/resource_manager.py` | - | Gregory 7.2 |
| Texture cache | `src/gui/gpu_renderer.py` | KotOR.js: texture manager | Gregory 7.2 |

### 14. Module Editor / Scene (Deliverable 6)
| Aspect | GhostRigger File | Reference Repo | Book |
|--------|-----------------|----------------|------|
| Scene graph | `src/core/scene_manager.py` | KotOR.js: scene management | Gregory 8.4 |
| Walkmesh | `src/core/scene_manager.py` | PyKotor: walkmesh resources | - |
| Module loading | `src/core/scene_manager.py` | KotOR.js: module loader | Gregory 7.2 |

---

## Bug Fix Cross-Reference

| Bug | Root Cause File | Fix Reference | Book Principle |
|-----|----------------|---------------|----------------|
| Texture wrapping on modules | `viewport.py` (_UV_SENTINEL=100.0, np.clip) | KotOR.js TPC wrap modes | Hayes Ch 7: GL_REPEAT via frac() |
| CPU perf / high RAM | `viewport.py` (painter's algo, MAX_TRIS=80000) | Switch to GPU renderer | Gregory 7.2: memory budgets, lazy loading |
| FBX export broken | `mesh_converter.py` (ASCII fallback) | ufbx skeletal structs, KotorBlender export | Mukundan 7.5: offset matrix, bind pose |
| Depth artifacts | `viewport.py` (painter's algo) | GPU z-buffer | Hayes Ch 13: GL_DEPTH_TEST |
| Inner geometry visible | `viewport.py` (no true z-buffer) | GPU depth testing | Hayes Ch 13: depth attachment |
