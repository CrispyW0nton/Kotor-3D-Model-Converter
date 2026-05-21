# Sprint 3.5 Phase 3.A Round-Trip Results

Date: 2026-05-21

Status: PASS

## Purpose

Phase 3.A verifies GhostRigger's MDL reader/writer self-consistency before any
more UE5-to-Aurora retargeting fixes are attempted. The gate asks whether stock
KOTOR models can be loaded and written back without semantic changes.

## Inputs

| Model | Purpose | Animation |
| --- | --- | --- |
| `tests/fixtures/kotor_stock/k1/S_Male02.mdl` | Local stock animation controller preservation | `pause1` |
| `tests/fixtures/kotor_stock/k1/pmbam.mdl` | Target body round-trip and inherited animation viewport playback | `victory` |

## Initial Failure Found

The first `S_Male02` run failed before comparison with a recursion error in the
binary animation writer. The stock `talk` animation has `anim_root=talkdummy`,
but `talkdummy` is a descendant of the true hierarchy root. The writer forced
the true root under `talkdummy`, producing:

```text
talkdummy -> S_Male02 -> cutscenedummy -> rootdummy -> ... -> head_g -> talkdummy
```

The writer now keeps the true hierarchy root as the serialized animation tree
root when `anim_root` is a descendant, while preserving the animation root name
in the animation header.

## Results

### `S_Male02` Local Animation Round-Trip

Command:

```powershell
python scripts/verify_roundtrip.py --input tests\fixtures\kotor_stock\k1\S_Male02.mdl --animation pause1 --output exports\verification\roundtrip\s_male02 --levels 1,2 --game k1
```

| Level | Result | Notes |
| --- | --- | --- |
| Level 1 byte identity | FAIL | Expected: writer canonicalizes layout and MDX payload. |
| Level 2 structural | PASS | 166/166 local animations preserved. |

Key metrics:

- Node count: match
- Local animation count: `166 -> 166`
- Requested animation local: `true`
- Max node position delta: `0.000e+00`
- Max node orientation delta: `0.000e+00`
- Max controller time delta: `0.000e+00`
- Max controller value delta: `0.000e+00`

Report: `exports/verification/roundtrip/s_male02/roundtrip_report.json`

### PMBAM Target Body Round-Trip

Command:

```powershell
python scripts/verify_roundtrip.py --input tests\fixtures\kotor_stock\k1\pmbam.mdl --animation victory --output exports\verification\roundtrip\pmbam --levels 1,2,3 --frames 0,30,60,90,120,150 --game k1
```

| Level | Result | Notes |
| --- | --- | --- |
| Level 1 byte identity | FAIL | Expected: writer canonicalizes layout and MDX payload. |
| Level 2 structural | PASS | PMBAM has 0 local animations; `victory` is inherited. |
| Level 3 viewport SSIM | PASS | All tested frames scored `1.00000`. |

Key metrics:

- Node count: match
- Local animation count: `0 -> 0`
- Requested animation local: `false`
- Max node position delta: `0.000e+00`
- Max node orientation delta: `0.000e+00`
- Frames tested: `0, 30, 60, 90, 120, 150`
- Min SSIM: `1.00000`

Report: `exports/verification/roundtrip/pmbam/roundtrip_report.json`

## Gate Decision

Phase 3.A passes.

GhostRigger's writer is not byte-identical to stock files, but it preserves
stock animation controller data structurally and preserves PMBAM inherited
`victory` playback visually. This clears the writer as the primary blocker for
continuing to Phase 3.B synthetic single-bone tests.

## Follow-Up

- Phase 3.B should now test retargeting math with synthetic one-bone FBX clips.
- KotorBlender cross-validation remains valuable as an external writer oracle,
  but Phase 3.A no longer indicates a GhostRigger writer halt.
