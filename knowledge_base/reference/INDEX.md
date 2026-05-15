# GhostRigger Knowledge Base Index
# Last Updated: 2026-04-13

## Project Identity
- **Name**: GhostRigger (Kotor 3D Model Converter)
- **Version**: 6.0.0
- **Repo**: https://github.com/CrispyW0nton/Kotor-3D-Model-Converter
- **License**: MIT
- **Python**: >= 3.10
- **Current State**: 174 tracked files, 75,513 LOC

## Knowledge Base Files

### Core References
| File | Purpose | When to read |
|------|---------|-------------|
| `MANDATORY_CHECKLIST.md` | Pre-task protocol | ALWAYS, before any task |
| `cross_reference_map.md` | Feature-to-repo-to-book mapping | When implementing any feature |
| `book_extracts.md` | Key principles from 3 reference books | When making architecture/algorithm decisions |
| `../roadmap/02_roadmap_2026_05.md` | Current Qt-branch roadmap (M0–M11) | When planning work order |
| `ROADMAP_legacy_2026_04.md` | Pre-Qt iteration roadmap (historical) | Background context only |

### Deliverable Knowledge Files (in `deliverables/`)
| File | Deliverable | Key Files Modified |
|------|------------|-------------------|
| `deliverables/d1_fbx_export.md` | FBX Export Fix | `src/converters/mesh_converter.py` |
| `deliverables/d2_texture_wrapping.md` | Texture Wrapping Fix | `src/gui/viewport.py` |
| `deliverables/d3_gpu_renderer.md` | GPU Renderer Foundation | `src/gui/gpu_renderer.py`, `src/gui/viewport.py` |
| `deliverables/d4_character_builder.md` | Character Builder Window | `src/gui/character_builder_window.py` |
| `deliverables/d5_performance.md` | Performance & Memory | `src/resources/resource_manager.py` |
| `deliverables/d6_module_scene.md` | Module Editor & Scene | `src/core/scene_manager.py` |

### Source Documentation (from handoff bundle, in `specs/`)
| File | Content |
|------|---------|
| `specs/ghostrigger_dev_prompt.md` | Master developer brief (Iteration 1 scope) |
| `specs/character_builder_spec.md` | Character Builder redesign spec |
| `specs/build_guide.md` | Architecture audit with 6-phase roadmap |
| `specs/architecture_audit.html` | Detailed codebase audit |
| `specs/README_manifest.txt` | Bundle manifest with all URLs |

### Spreadsheets (from handoff bundle, gitignored binary assets)
| File | Content |
|------|---------|
| `spreadsheets/feature_mapping.xlsx` | 26-row feature cross-reference matrix + bug fix guide |
| `spreadsheets/roadmap.xlsx` | 54-task breakdown, dependency graph, effort estimates |

### Reference Books (PDFs in `books/`, gitignored)
| Book | Author | Pages | Key Chapters for GhostRigger |
|------|--------|-------|------------------------------|
| `hayes_opengl_2025.pdf` | Wilson Hayes | ~300 | Ch 4 (VBO/VAO), Ch 7 (Textures), Ch 9 (Real-time), Ch 13 (Framebuffers) |
| `mukundan_mesh_animation_2022.pdf` | R. Mukundan | 209 | Ch 2 (Mesh formats), Ch 7 (Character Animation, Bones, Skinning) |
| `gregory_game_engine_arch_2024.pdf` | Jason Gregory | 628 | Ch 5 (3D Math), Ch 7 (Resource Manager), Ch 8 (Game/Render Loop) |

## Reference Repositories
| Priority | Repo | URL | Language | Primary Value |
|----------|------|-----|----------|--------------|
| 1 | ufbx | https://github.com/bqqbarbhg/ufbx | C | FBX skeletal structures |
| 2 | KotorBlender | https://github.com/seedhartha/kotorblender | Python | Armature, material, animation |
| 3 | KotOR.js | https://github.com/KobaltBlu/KotOR.js | TypeScript | GPU renderer, TPC/TXI parsers |
| 4 | PyKotor | https://github.com/OldRepublicDevs/PyKotor | Python | MDL, TPC, LIP resources |
| 5 | reone | https://github.com/seedhartha/reone | C++ | OpenGL graphics core |
| 6 | xoreos | https://github.com/xoreos/xoreos | C++ | Aurora model loading |
| 7 | FBX2glTF | https://github.com/facebookincubator/FBX2glTF | C++ | Conversion patterns |

## External Links
- Master Brief: https://www.genspark.ai/agents?id=c55f8d70-a7c1-439c-bb64-3d77ecf3b4d4
- Research Workspace 1: https://www.genspark.ai/agents?id=5a9bb414-d4e6-4f8c-8de1-4dbc092c374f
- Research Workspace 2: https://www.genspark.ai/agents?id=d4bd80fd-bd31-4858-b95c-e8b656ceba98
