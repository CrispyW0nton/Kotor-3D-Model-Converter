# Sprint 3 Reverse Retargeting Retrospective

Date: 2026-05-21

Status: R3.B/R3.C structurally complete; R4 blocked pending Sprint 3.5 Tier 3 viewport quality.

## What Worked

- The R3.A -> R3.B -> R3.C split isolated extraction, binary injection, and visual validation cleanly.
- Ghost Rigger's viewport caught the direct-world-rotation deformation immediately.
- Native `MDLBinaryWriter.write_files()` removed MDLEdit from the critical path.
- Local PMBAM `victory` override proved the inherited-supermodel slot strategy.
- Tests now cover coordinate conversion, animation writer behavior, extraction adaptation, and viewport validation.

## What Changed Mid-Sprint

The initial R3.B implementation wrote source world rotations directly into Aurora local controllers. The MDL loaded, but the viewport render showed catastrophic deformation. The fix was to compute source-local rest-relative rotation deltas from UE5 parent/rest transforms and apply those deltas onto PMBAM bind-local rotations.

This is the clearest validation of Locked Principle #11 so far: Blender is an authoring gate; Ghost Rigger viewport is the canonical MDL visual gate.

## Current Limits

- R3.B transfers core-body rotations only.
- Position controllers are omitted to preserve PMBAM proportions and keep output below the 2x size stop condition.
- Fingers, face, twist bones, richer head/neck transfer, and polished spine collapse are deferred.
- R3.C is a structural visual gate, not a final animation-quality gate.

## Course Correction

The original Tier 1 handoff threshold was rejected after reviewing viewport quality. That was the right correction: live KOTOR testing should validate engine fidelity, not absorb known retargeting-quality defects.

R4 is now blocked until the Ghost Rigger viewport shows Tier 3 quality: stable mesh, anatomically plausible idle pose, smooth motion, and no visible deformation. Sprint 3.5 owns that quality loop.
