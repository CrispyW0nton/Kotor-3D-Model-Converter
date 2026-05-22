# GhostRigger Book Notes

This directory is a tracked, searchable knowledge layer built from local
reference books. It is not a replacement for the books and does not copy their
content. It captures chapter maps, durable principles, and GhostRigger-specific
applications so future development can reuse the ideas quickly.

The binary PDFs remain outside git. The notes here are documentation only.

## Current Books

| Note | Source | Best Used For |
|------|--------|---------------|
| [`vince_mathematics_for_computer_graphics_7e.md`](vince_mathematics_for_computer_graphics_7e.md) | John Vince, *Mathematics for Computer Graphics*, 7th ed. | Foundational math, transforms, quaternions, interpolation, curves, barycentric coordinates, calculus/Fourier context. |
| [`gregory_game_engine_architecture_4e_vol1.md`](gregory_game_engine_architecture_4e_vol1.md) | Jason Gregory, *Game Engine Architecture*, 4th ed., Volume I PDF | Engine architecture, tools, asset pipelines, resource management, time/game loop, debugging/capture/profiling. |
| [`dunn_parberry_3d_math_primer_2e.md`](dunn_parberry_3d_math_primer_2e.md) | Dunn and Parberry, *3D Math Primer for Graphics and Game Development*, 2nd ed. | Practical coordinate spaces, vectors, matrices, rotation representations, geometric primitives, skeletal animation and graphics math. |
| [`ghostrigger_engine_crosswalk.md`](ghostrigger_engine_crosswalk.md) | Synthesizes all three | Which book concepts to use for each GhostRigger subsystem. |

## How To Use These Notes

Before changing code in a subsystem, check the crosswalk:

- **Animation and retargeting**: nested coordinate spaces, quaternion difference,
  orientation-vs-direction, pose/capture gates.
- **Rendering and skinning**: transforms, rigid matrices, normal/tangent bases,
  skinned mesh matrix palettes, visual debugging.
- **MDL/MDX resources**: resource identity, dependency/build rules, binary
  readback validation.
- **Tools and UI**: engine-tool architecture, logging, debug drawing, screenshots,
  non-blocking workflows.
- **Performance**: game-loop timing, profiling, resource loading, concurrency
  boundaries.

## Maintenance Rule

When a book concept affects a GhostRigger design decision, update the relevant
book note and the crosswalk. Keep entries factual, concise, and tied to a
subsystem or future test.
