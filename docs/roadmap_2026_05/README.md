# Roadmap 2026-05 — Qt Character Builder Re-design

This folder contains the post-Qt-migration roadmap for GhostRigger, derived from:

- Reallusion AccuRig HUD reference (user-supplied screenshot + video `e9AMHU_Dgf0`)
- Facial rigging tutorial (`pLRxzsPAqrE`)
- Stewart Jones, *Digital Creature Rigging: Wings, Tails & Tentacles* (CRC Press, 2019)
- A full audit of the `qt-ghostrigger` branch as of commit `3448116`
- The pre-existing `.ghostrigger_reference/docs/character_builder_spec.md`

## Files

| File | Purpose |
|------|---------|
| `01_qt_branch_audit.md` | Audit of the current Qt branch: Tk-vs-Qt status, module map, KOTOR model-type taxonomy, HUD design notes, Stewart Jones takeaways, gaps |
| `02_roadmap_2026_05.md` | Fresh M0–M11 roadmap with task IDs, hours, acceptance criteria, commit-message templates |

## Headline

1. **Qt is the only supported front-end.** Tk is frozen and removed by M3.
2. **Character Builder window matches the AccuRig HUD** (top toolbar / left rail / center viewport / right inspector / bottom strip).
3. **Four model-type modes** matching KOTOR's actual asset shapes:
   - Headless Body (e.g. `pmbam`, `pfbcm`)
   - Head (e.g. `pmhc01`, `pfhc01`)
   - Supermodel — Head + Headless composite snapped at `headhook`
   - Creature (e.g. `c_bantha`, `c_rancor`)
4. **Stewart Jones playbook** drives Creature mode: 3-Stage Asset Build, spline-IK chains, wing rig with FLAP/FOLD/LINK/CTRL layers, ROM test files.
5. **Validation surfaces live** through the bottom-strip banner.

## Critical path

`M0 → M1 → M2 → M4 → M5`  (~22-30 dev-days to a usable Headless Body workflow in the new shell)

Supersedes `.ghostrigger_reference/ROADMAP.md` for the Qt branch. The older roadmap is kept for historical reference only.
