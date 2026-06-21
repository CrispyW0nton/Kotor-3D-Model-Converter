# Learned Skills From Local Books

This file indexes practical skills distilled from the books in `docs/books`.
Use it as a routing map: load the smallest learned skill file that matches the
task, then return to the source PDFs only when deeper detail is needed.

## Source Library Map

- Rigging and deformation: `Digital_Creature_Rigging_-_Stewart_Jones.pdf`, `Rig_it_Right_Maya_Animation_Rigging_Concepts_-_Tina_OHailey.pdf`, `2017-tvc-automatic-skinning-weight-retargeting.pdf`.
- Meshes, vertices, transforms, and graphics math: `3D Math Primer for Graphics and Game Development 2nd Edition.pdf`, `Mathematics_for_Computer_Graphics_7E_-_John_Vince.pdf`, `Fundamentals_of_Computer_Graphics_-_Marschner_SteveShirley_Peter.pdf`, `Game_Engine_Architecture_4Ed_-_Jason_Gregory.pdf`, `3dsmax2020_ref_guide.pdf`, `3ds_Max_Basics_-_Bill_Culbertson.pdf`, `Autodesk_3ds_Max_2023_Bible_-_Seyi_Sunday.pdf`.
- Algorithms and computational geometry: `Algorithm_Design_-_Kleinberg.pdf`, `Computational_Geometry_-_Mark_de_Berg.pdf`, `Math_for_Programming_Early_Access_-_Ronald_T_Kneusel.pdf`.
- Rendering and shaders: `Computer_Graphics_Development_with_OpenGL_-_Wilson_Hayes.pdf`, `The_Book_of_Shaders_-_Patricio_Gonzalez_Vivo_and_Jen_Lowe.pdf`, `Fundamentals_of_Computer_Graphics_-_Marschner_SteveShirley_Peter.pdf`.
- Animation runtime: `Advanced_Animation_with_DirectX_Focus_on_Game_Development_-_Jim_Adams.pdf`, `3ds_Max_Basics_-_Bill_Culbertson.pdf`.
- Native C++ and embedded Python: `Professional_C_6th_Edition_-_Marc_Gregoire.pdf`, `Programming_C_C++.pdf`, `Systems_Programming_-_John_J_Donovan.pdf`, `Python_Cookbook_-_David_Beazley_Brian_K_Jones.pdf`, `Pro_Python_Experts_Voice_in_Open_Source_1st_Edition_-_Marty_Alchin.pdf`, `Dive_Into_Python_3_-_Mark_Pilgrim.pdf`, `Python_for_Dummies_-_Aahz_Maruch.pdf`.
- Unreal/editor and technical-art workflows: `Extending_and_Customizing_Unreal_Engine_Editor_-_Roger_Mattsson.pdf`, `Mastering_Technical_Art_in_Unreal_Engine_World_-_Greg_Penninck.pdf`, `Unreal_Engine_Blueprint_Game_Developer_-_Asadullah_Alam.pdf`.
- Game/audio design: `Designing_games_-_Tynan_Sylvester.pdf`, `Game_Audio_Programming_-_Guy_Somberg.pdf`.
- Qt and UI workflow: `Create_GUI_Applications_with_Python_n_Qt6_-_Martin_Fitzpatrick.pdf`, `Mark Summerfield - Rapid GUI Programming with Python and Qt.pdf`, `Qt_6_C_GUI_Programming_Cookbook_3rd_Edition_-_Lee_Zhi_Eng.pdf`, `Refactoring_UI_-_Steve_Schoger.pdf`.
- Architecture and service boundaries: `Architecture_Patterns_with_Python_-_Bob_Gregory.pdf`, `Clean_Architecture_-_Robert_C_Marti.pdf`, `Game_Engine_Architecture_4Ed_-_Jason_Gregory.pdf`.
- MCP and AI/backend validation: `Model_Context_Protocol_for_LLMs_-_Naveen_Krishnan.pdf`, `Mastering_Model_Context_Protocol_Advanced_Techniques_for_AI_Integration_-_Kevin_Lowe.pdf`.

## Skill Index

- `learned/meshskill.md`: Use for mesh inspection, topology bugs, face/edge/normal issues, viewport mesh diagnostics, import cleanup, and mesh-render-data contracts.
- `learned/vertexskill.md`: Use for vertex transforms, normals, barycentric/intersection math, skin weights, vertex identity, and per-vertex validation.
- `learned/extrusionskill.md`: Use for extrusion, bevel, inset, edge-loop, face-creation, and generated-geometry tools.
- `learned/transformskill.md`: Use for coordinate spaces, matrices, quaternions, pivots, object/world/local conversions, camera math, and animation transforms.
- `learned/riggingskill.md`: Use for joints, bones, skeleton hierarchy, controller behavior, skinning, weight transfer, deformation cleanup, and animation rig checks.
- `learned/qtuiskill.md`: Use for PySide6/Qt widgets, signals, model/view, long-running GUI tasks, custom widgets, theming, layout, and visual workflow tests.
- `learned/architectureskill.md`: Use for deciding whether behavior belongs in core, systems, adapters, GUI, native packages, or tests.
- `learned/mcpvalidationskill.md`: Use for backend/model-pipeline validation tools, MCP server/tool design, and context-safe validation workflows.
- `learned/resourceskill.md`: Use for assets, resource managers, file systems, texture/material residency, and pipeline handoff.
- `learned/algorithmgeometryskill.md`: Use for graph/search/flow/dynamic-programming choices, sweep-line geometry, point location, Delaunay/Voronoi reasoning, and robust geometric predicates.
- `learned/renderingshaderskill.md`: Use for OpenGL/D3D-style pipelines, buffers, shader stages, GLSL, lighting, shadow, framebuffer, post-process, and GPU debugging work.
- `learned/animationruntimeskill.md`: Use for time-based animation, skeletal hierarchies, keyframes, animation sets, skinned meshes, frame updates, and runtime pose evaluation.
- `learned/cppnativeskill.md`: Use for C++ package work, ABI boundaries, RAII, memory ownership, DLL exports, C interfaces, and systems/native-host concerns.
- `learned/pythonskill.md`: Use for Pythonic implementation, iterators/generators, file/IO, modules/packages, testing/debugging, C extensions, and embedded Python payload care.
- `learned/unrealskill.md`: Use for Unreal/editor integration, plugins, editor modes/windows, Slate-style tooling, Blueprints, world blockout, landscapes, materials, and technical-art handoff.
- `learned/gamedesignskill.md`: Use for workflow and tool design through mechanics, feedback, difficulty, narrative/task flow, playtest loops, and user motivation.
- `learned/audioskill.md`: Use for audio/event tooling, dynamic mixing, randomization, music state, thread-safe command buffers, footsteps/foley, and debugging audio-like event systems.

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
