# R4 Ghost Rigger UE5 Idle Live Test Handoff

Status: HELD. Do not hand off for live testing until Tier 3 viewport quality passes. See `STATUS_HELD_PENDING_TIER3.md`.

This package is for a proof-of-pipeline live KOTOR test. It is not an animation-quality acceptance package.

## Objective

Validate the full integration loop:

`UE5 FBX -> Ghost Rigger reverse retarget -> Aurora PMBAM MDL/MDX -> Patch Manager install -> KOTOR runtime animation trigger`

## Success Threshold

Tier 1 is success for R4: the `victory` animation plays in-game at all, even if visual quality is rough.

Animation polish is deferred to Sprint 4.

## Package Contents

- `manifest.json` - Patch Manager test manifest
- `files/override/pmbam.mdl` - PMBAM with local `victory` override
- `files/override/pmbam.mdx` - paired MDX emitted by Ghost Rigger writer
- `baseline/vanilla_pmbam.mdl` - vanilla PMBAM rollback reference
- `baseline/vanilla_pmbam.mdx` - vanilla PMBAM MDX rollback reference
- `ghostrigger_injection_manifest.json` - R3.B injection manifest
- `viewport_validation_report.json` - R3.C Ghost Rigger viewport validation report
- `media/viewport_frame_0150.png` - viewport frame 150 reference capture
- `tests/verify_install.py` - simple installed override hash verifier
- `R4_LIVE_TEST_PROMPT.md` - execution protocol

## SHA-256

Complete handoff checksums are in `SHA256SUMS.txt`. That file excludes itself.

| File | SHA-256 |
|---|---|
| `files/override/pmbam.mdl` | `bfcd3468838050d25159afa3c90d963fec1a06fcbfc64b6ea9982adc4a8be8df` |
| `files/override/pmbam.mdx` | `84dc9b42faa0b2004c0e10eef6ab0bc65e02ee7bffaca027b829574832a58154` |
| `baseline/vanilla_pmbam.mdl` | `f439fbdbf9e50ef994d14c333d0829017ad72bcfc1bf6f922420943e37ebf3f1` |
| `baseline/vanilla_pmbam.mdx` | `a912c9fb3f8e785f06652e778295ebe6655d20fdb82a437456cd71939b4c6b22` |
| `ghostrigger_injection_manifest.json` | `c910363dda141c2e76493d5e85f54ada45cfb9e7b628a50e1b4cf669dbb916ba` |
| `viewport_validation_report.json` | `fac8c5ce23774a87b9ae7ca646d9266e03cd8cdac147b573dae2df2da2ee7eb4` |
| `media/viewport_frame_0150.png` | `0061e6c07c462afef569ff9204287037b4381890d3fb0e0d5f40225a83bf1c2a` |

## Known Limitations

- Core-body rotation transfer only: 20 mapped Aurora bones.
- No translation/root motion controllers in R3.B.
- Fingers, face, twist bones, and richer neck/head mapping are deferred.
- Spine collapse is first-pass policy work.

Expected visual roughness should be documented, not treated as a blocker for Tier 1.
