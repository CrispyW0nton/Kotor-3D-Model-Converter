# Sprint 3.5 Quality Gate Principle

Date: 2026-05-21

Status: Locked

## Locked Principle #12

Live in-game testing is reserved for engine fidelity validation only. Animation quality, retargeting correctness, and visual fidelity must reach Tier 3 in Ghost Rigger viewport before any live test is conducted.

## Rationale

- Ghost Rigger viewport is the canonical visual validator for MDL output.
- Live tests are slower and produce ambiguous failure signals when quality bugs are still present.
- Retargeting quality defects are faster to diagnose through viewport captures, validation JSON, and bone-position reports.
- Patch Manager and Custom Animation Core test cycles should validate install/runtime integration, not absorb known retargeting-quality failures.

## Immediate Impact

- R4 Patch Manager live test is blocked until the Sprint 3.5 quality gate passes.
- The existing R4 handoff package is held as a draft/test artifact only.
- Sprint 3.5 focuses on viewport-only quality iteration before handoff.

## Locked Principle #13

Production-quality animation output requires ground-truth verification, not
visual heuristics.

## Rationale

- A renderable animation can still be mathematically wrong.
- UE5-to-KOTOR retargeting has no established community recipe to copy.
- Writer correctness, transform correctness, external writer parity, and visual
  quality need independent oracles so failures can be isolated by subsystem.
- Phase 3.5 therefore gates further quality work on reader/writer round-trip,
  synthetic transform tests, KotorBlender comparison when available, and viewport
  validation.
