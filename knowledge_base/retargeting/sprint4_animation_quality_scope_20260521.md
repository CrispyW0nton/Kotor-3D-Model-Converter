# Sprint 4 Animation Quality Scope

Date: 2026-05-21

Status: Superseded by Sprint 3.5 quality gate. R4 is not handed off until Tier 3 viewport quality passes.

## Goal

Improve UE5-to-Aurora animation quality before R4 live engine integration.

## Candidate Work Items

1. Add controlled translation/root-motion transfer.
   - Start with pelvis/root deltas only.
   - Add gates for size growth and ground penetration.

2. Expand hand/finger coverage.
   - Decide whether PMBAM finger nodes can receive Manny finger curves directly.
   - Add per-chain validation so omitted fingers are explicit, not silent.

3. Improve neck/head transfer.
   - Handle `neck_02` collapse intentionally.
   - Add head look/aim preservation tests.

4. Add per-bone source-to-target local-basis remapping.
   - Highest-priority Sprint 3.5 finding.
   - Convert source local animation deltas into Aurora local bone axes before applying them to target bind rotations.

5. Replace Policy A spine collapse with weighted or chain-composed transfer.
   - Compare deepest-source, parent-source, and distributed spine policies in viewport.

6. Add motion quality metrics.
   - Bone angle continuity.
   - Per-frame quaternion delta limits.
   - Viewport capture comparisons against a chosen target reference.

7. Add optional one-FBX-animation-to-one-Aurora-slot batch harness.
   - Useful before multi-character or full-library export.

## Non-Goals

- Do block R4 on Tier 3 viewport quality.
- Do not automate KOTOR in-game capture yet.
- Do not broaden to all player body models until PMBAM quality improves.
