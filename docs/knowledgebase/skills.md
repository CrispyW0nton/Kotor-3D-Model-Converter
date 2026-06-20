# Learned Skills From Local Books

This file indexes practical skills distilled from the books in `docs/books`.
Use it as a routing map: load the smallest learned skill file that matches the
task, then return to the source PDFs only when deeper detail is needed.

## Source Library Map

- Rigging and deformation: `Digital_Creature_Rigging_-_Stewart_Jones.pdf`, `Rig_it_Right_Maya_Animation_Rigging_Concepts_-_Tina_OHailey.pdf`, `2017-tvc-automatic-skinning-weight-retargeting.pdf`.
- Meshes, vertices, transforms, and graphics math: `3D Math Primer for Graphics and Game Development 2nd Edition.pdf`, `Mathematics_for_Computer_Graphics_7E_-_John_Vince.pdf`, `Game_Engine_Architecture_4Ed_-_Jason_Gregory.pdf`, `3dsmax2020_ref_guide.pdf`.
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

## General Learned Operating Rules

- Start from the owning layer. Put reusable behavior in `src/core`, `src/systems`, `src/adapters`, `src/math`, `src/io`, `src/formats`, or `src/resources` before wiring GUI callers.
- Keep visual/UI changes visibly tested in the real application. Backend probes and MCP tools confirm data truth, not workflow usability.
- Preserve coordinate-space intent. Always name whether a value is object, local, parent, world, camera, screen, bind, or pose space.
- Treat rigs as layered assets: cleaned source geometry, base skeleton/skin, animation controls, deformation polish, and final cleanup are separate concerns.
- Treat mesh edits as topology contracts. Validate face winding, open edges, duplicate/isolated vertices, missing UVs, flipped normals, and stable IDs before trusting the result.
- Prefer targeted tests. For book-derived changes, pair one headless contract check with one visible workflow check when the behavior reaches UI.
- Keep UI systems dense and readable. Use hierarchy, spacing, contrast, and theme/layout tokens rather than one-off colors or fixed sizes.
- Use progressive disclosure for agent knowledge: this index stays small; learned files hold topic-specific workflows; source PDFs are the final reference.
