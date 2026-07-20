# Learned Skills From Local Books

This file indexes practical skills distilled from the books in `docs/books`.
Use it as a routing map: load the smallest learned skill file that matches the
task, then return to the source PDFs only when deeper detail is needed.

## Source Library Map

- Coupling, cohesion, and software design: `Balancing_Coupling_in_Software_Design_-_Vlad_Khononov.pdf`, `Structured_design_-_Larry_L_Constantine.pdf`, `Software_Design_for_Python_Programmers_Final_-_Ronald_Mak.pdf`, `Clean_Architecture_-_Robert_C_Marti.pdf`, `Architecture_Patterns_with_Python_-_Bob_Gregory.pdf`.
- Advanced Python engineering: `Advanced_Python_Programming_-_Quan_Nguyen.pdf`, `Expert_Python_Programming_-_Tarek_Ziade.pdf`, `Python_Cookbook_-_David_Beazley_Brian_K_Jones.pdf`, `Dive_Into_Python_3_-_Mark_Pilgrim.pdf`, `Mastering_Python_Design_Patterns_-_Sakis_Kasampalis.pdf`.
- Rigging and deformation: `Digital_Creature_Rigging_-_Stewart_Jones.pdf`, `Rig_it_Right_Maya_Animation_Rigging_Concepts_-_Tina_OHailey.pdf`, `Inspired 3d advanced rigging and deformations (Clark, Brad) (z-library.sk, 1lib.sk, z-lib.sk).pdf`, `2017-tvc-automatic-skinning-weight-retargeting.pdf`.
- Technical animation and mesh processing: `Technical_Animation_in_Video_Games_-_Matthew_Lake.pdf`, `3D_Mesh_Processing_and_Character_-_Ramakrishnan_Mukundan.pdf`, `Unreal_Engine_5_Character_Creation_Animation_and_Cinematics_-_Henk_Venter.pdf`.
- Meshes, vertices, transforms, and graphics math: `3D Math Primer for Graphics and Game Development 2nd Edition.pdf`, `Mathematics_for_Computer_Graphics_7E_-_John_Vince.pdf`, `Fundamentals_of_Computer_Graphics_-_Marschner_SteveShirley_Peter.pdf`, `Game_Engine_Architecture_4Ed_-_Jason_Gregory.pdf`.
- Algorithms and computational geometry: `Algorithm_Design_-_Kleinberg.pdf`, `Computational_Geometry_-_Mark_de_Berg.pdf`, `Math_for_Programming_Early_Access_-_Ronald_T_Kneusel.pdf`.
- Rendering and shaders: `Computer_Graphics_Development_with_OpenGL_-_Wilson_Hayes.pdf`, `The_Book_of_Shaders_-_Patricio_Gonzalez_Vivo_and_Jen_Lowe.pdf`, `Fundamentals_of_Computer_Graphics_-_Marschner_SteveShirley_Peter.pdf`.
- PBR texturing and Blender pipeline: `Beginning_PBR_Texturing_-_Abhishek_Kumar.pdf`, `Learning_Blender_-_Oliver_Villar.pdf`.
- Animation runtime: `Advanced_Animation_with_DirectX_Focus_on_Game_Development_-_Jim_Adams.pdf`.
- Native C++ and game programming: `Professional_C_6th_Edition_-_Marc_Gregoire.pdf`, `Practical_C_Game_Programming_-_Zhenyu_George_Li.pdf`, `Programming_C_C++.pdf`, `Systems_Programming_-_John_J_Donovan.pdf`.
- Unreal/editor and technical-art workflows: `Extending_and_Customizing_Unreal_Engine_Editor_-_Roger_Mattsson.pdf`, `Mastering_Technical_Art_in_Unreal_Engine_World_-_Greg_Penninck.pdf`, `Unreal_Engine_Blueprint_Game_Developer_-_Asadullah_Alam.pdf`.
- Level design and procedural generation: `Architectural_Approach_to_Level_Design_-_Christopher_Totten.pdf`, `Level_Design_for_Games_-_Phil_Co.pdf`, `Procedural_Content_Generation_-_Paul_Martin_Eliasz.pdf`.
- Game/audio design: `Designing_games_-_Tynan_Sylvester.pdf`, `Game_Audio_Programming_-_Guy_Somberg.pdf`.
- Qt and UI workflow: `Create_GUI_Applications_with_Python_n_Qt6_-_Martin_Fitzpatrick.pdf`, `Mark Summerfield - Rapid GUI Programming with Python and Qt.pdf`, `Qt_6_C_GUI_Programming_Cookbook_3rd_Edition_-_Lee_Zhi_Eng.pdf`, `Refactoring_UI_-_Steve_Schoger.pdf`.
- MCP and AI/backend validation: `Model_Context_Protocol_for_LLMs_-_Naveen_Krishnan.pdf`, `Mastering_Model_Context_Protocol_Advanced_Techniques_for_AI_Integration_-_Kevin_Lowe.pdf`.
- Coupling and module-boundary design (2026-06): `Balancing_Coupling_in_Software_Design_-_Vlad_Khononov.pdf`, `Structured_design_-_Larry_L_Constantine.pdf`.
- Advanced Python engineering (2026-06): `Advanced_Python_Programming_-_Quan_Nguyen.pdf`, `Expert_Python_Programming_-_Tarek_Ziade.pdf`, `Mastering_Python_Design_Patterns_-_Sakis_Kasampalis.pdf`.
- Technical animation and mesh processing (2026-06): `Technical_Animation_in_Video_Games_-_Matthew_Lake.pdf`, `_OceanofPDF.com_3D_Mesh_Processing_and_Character_-_Ramakrishnan_Mukundan.pdf`.
- Unreal character/animation pipeline (2026-06): `_OceanofPDF.com_Unreal_Engine_5_Character_Creation_Animation_and_Cinematics_-_Henk_Venter.pdf`.
- Blender DCC handoff (2026-06): `_OceanofPDF.com_Learning_Blender_-_Oliver_Villar.pdf`.
- PBR textures and materials (2026-06): `_OceanofPDF.com_Beginning_PBR_Texturing_-_Abhishek_Kumar.pdf`.
- Level and map design (2026-06): `Architectural_Approach_to_Level_Design_-_Christopher_Totten.pdf`, `Level_Design_for_Games_-_Phil_Co.pdf`.
- Procedural generation (2026-06): `Procedural_Content_Generation_-_Paul_Martin_Eliasz.pdf`.
- C game-engine architecture (2026-06): `Practical_C_Game_Programming_-_Zhenyu_George_Li.pdf`.
- Binary analysis and Radare2 (2026-07 external study):
  `_OceanofPDF.com_Practical_Binary_Analysis_-_Dennis_Andriesse.pdf`,
  `_OceanofPDF.com_Radare2_in_Action_A_Practical_Guide_to_Open-Source_Binary_Analysis_The_Ultimate_Reverse_Engineering_Guide_From_Beginner_to_Expert_-_Soren_Veyron.pdf`.

## Skill Index

### Architecture, Coupling, and Python Engineering (2026-06 books)

- `learned/couplingdesignskill.md`: Use when deciding package merge/split/move, evaluating coupling dimensions (strength, distance, volatility, type, cost), rebalancing drifted coupling, or auditing empty Domain.Core.* stubs. Grounded in Khononov's *Balancing Coupling* and Constantine's *Structured Design*.
- `learned/couplingskill.md`: Use for the connascence taxonomy, seven cohesion levels, and patterns-as-boundary-tools. The *what kind of coupling is this?* companion to the design skill.
- `learned/architectureskill.md`: Use for deciding whether behavior belongs in core, systems, adapters, GUI, native packages, or tests. Covers layering patterns, ports/adapters, service layer, repository pattern.
- `learned/pythonengineeringskill.md`: Use for Python profiling/optimization (cProfile, line_profiler, memory_profiler), NumPy vectorization of vertex/skin math, concurrency (asyncio, multiprocessing), ctypes DLL bridges, embedded payload packaging (18 DLL manifest system), and design patterns in Python. Grounded in Nguyen's *Advanced Python Programming*, Ziade's *Expert Python Programming*, and Mak's *Software Design for Python Programmers*.
- `learned/advancedpythonskill.md`: Use for Cython, Numba, exploring compilers, JAX, concurrent web requests, concurrent image processing, GIL internals, deadlock/race-condition analysis. Deep companion to the engineering skill.
- `learned/pythonpackagingskill.md`: Use for the payload manifest system, setup.cfg, entry points, distribution, and the native_python_payload_generator workflow.
- `learned/pythonskill.md`: Use for Pythonic implementation, iterators/generators, file/IO, modules/packages, testing/debugging, C extensions, and embedded Python payload care.

### Animation, Rigging, Mesh, and Texture Pipeline (2026-06 books)

- `learned/technicalanimationskill.md`: Use for technical animation pipeline decisions: MoCap data handling, skeleton/skin export pipeline, animation state machines, retargeting pipeline architecture, LOD strategies, animation performance profiling, and the native Odyssey DAG lock (T2501-T2505). Grounded in Lake's *Technical Animation in Video Games*, Mukundan's *3D Mesh Processing*, and Venter's *UE5 Character Creation*.
- `learned/riggingskill.md`: Use for joints, bones, skeleton hierarchy, controller behavior, skinning, weight transfer, deformation cleanup, and animation rig checks.
- `learned/skinningdeformationskill.md`: Use for Character Builder skinning failures where skeleton generation succeeds but imported source weights, donor transfer, deformation ROM, bind pose, bone palette, or corrective deformation behavior is suspect.
- `learned/characterbuilderprinciples.md`: Use before changing Character Builder import, skeleton fitting, binding, weight transfer, deformation preview, animation proof, or MDL export behavior.
- `learned/unrealcharacterpipelineskill.md`: Use for the UE5 retarget lane (IK Rig, Retargeter, Control Rig, Sequencer, MetaHuman, Mixamo retarget workflow).
- `learned/meshskill.md`: Use for mesh inspection, topology bugs, face/edge/normal issues, viewport mesh diagnostics, import cleanup, and mesh-render-data contracts.
- `learned/meshprocessingskill.md`: Use for half-edge data structures, mesh simplification/subdivision, parameterization, 3D morphing, and geometry shader algorithms. Grounded in Mukundan's *3D Mesh Processing*.
- `learned/vertexskill.md`: Use for vertex transforms, normals, barycentric/intersection math, skin weights, vertex identity, and per-vertex validation.
- `learned/extrusionskill.md`: Use for extrusion, bevel, inset, edge-loop, face-creation, and generated-geometry tools.
- `learned/transformskill.md`: Use for coordinate spaces, matrices, quaternions, pivots, object/world/local conversions, camera math, and animation transforms.
- `learned/pbrtexturingskill.md`: Use for PBR texturing workflow, mesh map baking, UV mapping validation, Blender/Maya FBX export with axis conversion, texel density, texture slot replacement in MDL files, and TPC/TGA decoding. Grounded in Kumar's *Beginning PBR Texturing* and Villar's *Learning Blender*.
- `learned/blenderpipelineskill.md`: Use for Blender UV unwrapping, materials/shaders, FBX export, keyframe animation, and Python scripting for batch operations.
- `learned/renderingshaderskill.md`: Use for OpenGL/D3D-style pipelines, buffers, shader stages, GLSL, lighting, shadow, framebuffer, post-process, and GPU debugging work.

### Level Design, Map Studio, and Procedural Generation (2026-06 books)

- `learned/leveldesignskill.md`: Use for Map Studio room/area authoring decisions, module layout design, LYT/VIS/WOK spatial planning, gameplay placement strategy, grayboxing, and modular room construction. Grounded in Totten's *Architectural Approach to Level Design*, Phil Co's *Level Design for Games*, and Eliasz's *Procedural Content Generation*.
- `learned/kotorwalkmeshcontract.md`: Use for K1/K2 WOK/BWM reading, fidelity round trips, walkmesh generation, adjacency and perimeter repair, AABB construction, holes/islands, header-vector preservation, visual-only classification, converted-module walkmesh audits, and the structural-to-retail proof ladder. Grounded in exhaustive vanilla K1/K2 WOK censuses and named engine-era exceptions.
- `learned/kotormaxlegacyroomrecovery.md`: Use when recovering KOTOR rooms from legacy 3ds Max/NWMax scenes, KOTORMax fallback exports, or historical sanity manifests. Covers scripted-plugin class/superclass compatibility, lossless first-open discipline, non-destructive partition reconstruction, Vul803 room-role evidence, controller-free compilation, and the vanilla-to-retail proof ladder.
- `learned/proceduralgenerationskill.md`: Use for ISM/HISM instancing for performance, PCG graph systems, spline-driven generation, animated crowd spawning, and performance budgeting. Grounded in Eliasz's *Procedural Content Generation with UE5*.
- `learned/gamedesignskill.md`: Use for workflow and tool design through mechanics, feedback, difficulty, narrative/task flow, playtest loops, and user motivation.

### Native C++ and Systems (2026-06 books)

- `learned/gamecppskill.md`: Use for C++ rendering pipeline decisions, game-loop architecture, camera systems in native code, animation FSMs, performance-critical native code, procedural generation algorithms, and the native host launch flow. Grounded in Li's *Practical C++ Game Programming* and Somberg's *Game Audio Programming*.
- `learned/cgameprogrammingskill.md`: Use for organizing the runtime: kernel/subsystem split, scene composition, resource lifecycle, and C++ game architecture patterns.
- `learned/cppnativeskill.md`: Use for C++ package work, ABI boundaries, RAII, memory ownership, DLL exports, C interfaces, and systems/native-host concerns.
- `learned/animationruntimeskill.md`: Use for time-based animation, skeletal hierarchies, keyframes, animation sets, skinned meshes, frame updates, and runtime pose evaluation.

### Cross-Cutting Skills

- `kotorghidraskill.md`: Use before expanding Map Studio PIE focus, interaction, combat, dialogue, camera, audio, inventory, or HUD behavior. It makes the analyzed retail Odyssey runtime the behavioral specification, requires engine evidence/file evidence/editor inference to stay separately labeled, and keeps manual K1/K2 proof authoritative.
- `learned/binaryanalysisskill.md`: Use for corrupt MOD/ERF/RIM/GFF/MDL/MDX/WOK triage, header/table validation, carving, vanilla binary comparison, safe fixed-length patching, recovery provenance, executable crash slicing, and the proof ladder that separates parser acceptance from retail-game truth. Grounded in Andriesse's *Practical Binary Analysis* and Ghost Studio's established KOTOR loader findings.
- `learned/radare2skill.md`: Use for version-checked Radare2 read-only triage, metadata/section/string/function/xref navigation, r2pipe evidence capture, bounded debugging, cache-first patch proposals, and KOTOR-specific escalation to Ghidra/Capstone/live proof. Exact commands must be checked against the installed Radare2 version and official documentation.
- `learned/qtuiskill.md`: Use for PySide6/Qt widgets, signals, model/view, long-running GUI tasks, custom widgets, theming, layout, and visual workflow tests.
- `learned/mcpvalidationskill.md`: Use for backend/model-pipeline validation tools, MCP server/tool design, and context-safe validation workflows.
- `learned/kotormcp_live_game_proofskill.md`: Use for real KOTOR 1/KOTOR 2 runtime proof with KotorMCP, the DirectInput `dinput8.dll` proxy hook, live debug-event logs, Ghidra crash-address annotation, save-load/warp testing, and Map Studio or Character Builder in-game evidence.
- `learned/resourceskill.md`: Use for assets, resource managers, file systems, texture/material residency, and pipeline handoff.
- `learned/algorithmgeometryskill.md`: Use for graph/search/flow/dynamic-programming choices, sweep-line geometry, point location, Delaunay/Voronoi reasoning, and robust geometric predicates.
- `learned/unrealskill.md`: Use for Unreal/editor integration, plugins, editor modes/windows, Slate-style tooling, Blueprints, world blockout, landscapes, materials, and technical-art handoff.
- `learned/audioskill.md`: Use for audio/event tooling, dynamic mixing, randomization, music state, thread-safe command buffers, footsteps/foley, and debugging audio-like event systems.

### Advanced Skills (2026-06 expansion)

- `learned/couplingskill.md`: Use for package-boundary decisions, the 109-package triage, merging empty/duplicate native packages, API-contract design, and the connascence/cohesion lens behind `package_ownership_model.md`. Pairs with `architectureskill.md`.
- `learned/advancedpythonskill.md`: Use for the embedded Python host internals (custom meta-path importer, DLL RCDATA payload loading), C/ctypes interop, the GIL, multiprocessing/threading for non-blocking scans/imports/exports, and profiling. Companion to `pythonskill.md`.
- `learned/pythonpackagingskill.md`: Use for the embedded Python payload packaging pipeline (manifests, `.rc` resources, byte-identity tests) and the design patterns that structure the codebase: Command (the T2307 undo foundation), Strategy/Adapter/Facade/Bridge for renderer backends and viewport shims.
- `learned/technicalanimationskill.md`: Use for the Character Studio native Odyssey DAG lock (T2501-T2505), skeletal data structures, joint orientation, offset/bind matrix + LBS math, ROM tests, supermodel inheritance, and runtime pose evaluation. Pairs with `riggingskill.md` and `animationruntimeskill.md`.
- `learned/meshprocessingskill.md`: Use for mesh topology/manifold analysis, half-edge/DCEL adjacency, normal/tangent computation, simplification/QEM, and the AGENTS.md topology contracts (winding, open edges, duplicates, UVs, T-vertices). Pairs with `meshskill.md` and `vertexskill.md`.
- `learned/unrealcharacterpipelineskill.md`: Use for the Retarget Studio KOTOR-to-Unreal lane (T2404): UE5 IK Rig/Retargeter, chain mapping, base-pose alignment, FBX handoff, and the Quinn/Odyssey skeleton-map. Pairs with `unrealskill.md`.
- `learned/blenderpipelineskill.md`: Use for the Character Studio Blender FBX/OBJ import path, armature/bone model (deform vs control bones), bone roll, vertex groups → skin rows, and the `x, z, -y` axis conversion.
- `learned/pbrtexturingskill.md`: Use for KOTOR texture/material discipline (TGA/TPC/TXI), PBR channel separation, mesh-map baking, the Stock Module Editor material-slot replacement, and the renderer texture-upload/lifecycle separation in AGENTS.md. Pairs with `resourceskill.md` and `renderingshaderskill.md`.
- `learned/leveldesignskill.md`: Use for Map Studio and Module Studio area authoring: spatial design, flow/sightlines/pacing, modular kits, blockout/greybox, encounter placement, LYT/VIS composition, and the `grdev01` golden-package goal (T3105). Pairs with `gamedesignskill.md`.
- `learned/proceduralgenerationskill.md`: Use for the Map Studio terrain builder (T2907): heightfields, seeded presets, slope diagnostics, co-generated WOK, and when PG helps vs hurts hand-authored KOTOR content.
- `learned/cgameprogrammingskill.md`: Use for the game-engine architecture of GhostRigger's native runtime: game-loop structure, scene/entity/component composition, resource lifecycle phases, rendering pipeline organization, and camera systems. Companion to `cppnativeskill.md`.

## GhostRigger Map Studio Skill Index

These older top-level skill files remain useful while Map Studio is being
productized. Use them alongside the newer `learned/` files when the task touches
KOTOR-specific map construction, terrain, component editing, or export honesty.

- `meshskill.md`: mesh representation, topology, object boundaries, exportable KOTOR room/object geometry, UV/DCC handoff.
- `vertexskill.md`: vertex/edge/face component editing, snapping, welding, selection, validation, and undo expectations.
- `extrusionskill.md`: extrusion, bevel, inset, bridge, boolean, split/fill, and cleanup tools for Map Studio.
- `toolbeltskill.md`: Maya-like action belts, command keys, customization, mode grouping, shortcuts, and workflow-specific UI ownership.
- `objectseparationskill.md`: separate/combine, object identity, resource ownership, DCC/UV handoff, and KOTOR export boundary readiness.
- `computationalgeometryskill.md`: robust predicates, polygon operations, spatial queries, triangulation, tolerances, and degeneracy handling.
- `terrainsculptskill.md`: low-latency terrain sculpting, heightfields, brush coalescing, dirty regions, walkability/WOK validation.
- `uvtextureskill.md`: UV preservation, material slots, texture references, lightmap/secondary UV policy, and DCC round-trip constraints.
- `riggingskill.md`: Character Builder skeleton fitting, binding, skinning, deformation preview, donor weights, and export preflight.
- `qtuiskill.md`: Qt actions, model/view, threading, undo, theming, and studio/window boundaries.
- `mathskill.md`: coordinate spaces, matrices, quaternions, transforms, geometry tests, and determinant/handedness checks.
- `performanceskill.md`: no-lag interaction design, coalescing, caching, async jobs, bounded budgets, and validation cadence.
- `mapstudioskill.md`: Maya/ZBrush-inspired Map Studio workspace rules tied to KOTOR authored resources, validation, export readiness, and game proof.

Before implementing a feature, name the owning studio/window, owning package,
book-derived skill, KOTOR validation/export gate, and capability stage.

## General Learned Operating Rules

- Start from the owning layer. Put reusable behavior in `src/core`, `src/systems`, `src/adapters`, `src/math`, `src/io`, `src/formats`, or `src/resources` before wiring GUI callers.
- Keep visual/UI changes visibly tested in the real application. Backend probes and MCP tools confirm data truth, not workflow usability.
- Preserve coordinate-space intent. Always name whether a value is object, local, parent, world, camera, screen, bind, or pose space.
- Treat rigs as layered assets: cleaned source geometry, base skeleton/skin, animation controls, deformation polish, and final cleanup are separate concerns.
- Treat mesh edits as topology contracts. Validate face winding, open edges, duplicate/isolated vertices, missing UVs, flipped normals, and stable IDs before trusting the result.
- Prefer targeted tests. For book-derived changes, pair one headless contract check with one visible workflow check when the behavior reaches UI.
- Keep UI systems dense and readable. Use hierarchy, spacing, contrast, and theme/layout tokens rather than one-off colors or fixed sizes.
- For algorithms and geometry, handle degeneracy/robustness deliberately before optimizing.
- For renderer work, separate CPU asset truth, GPU resource state, shader inputs, draw submission, and post-process passes.
- For native C++ work, define ownership and ABI boundaries before implementation; keep Python payload copies generated from canonical sources.
- Use progressive disclosure for agent knowledge: this index stays small; learned files hold topic-specific workflows; source PDFs are the final reference.
