# Roadmap 2026-05 — Qt Character Builder Re-design

This folder contains the post-Qt-migration roadmap for GhostRigger, derived from:

- Reallusion AccuRig HUD reference (user-supplied screenshot + video `e9AMHU_Dgf0`)
- Facial rigging tutorial (`pLRxzsPAqrE`)
- Stewart Jones, *Digital Creature Rigging: Wings, Tails & Tentacles* (CRC Press, 2019)
- A full audit of the `qt-ghostrigger` branch (last refreshed 2026-05-15, post-M5)
- The pre-existing `knowledge_base/reference/specs/character_builder_spec.md`

## Files

| File | Purpose |
|------|---------|
| `01_qt_branch_audit.md` | Audit of the current Qt branch: Tk-vs-Qt status, module map, KOTOR model-type taxonomy, HUD design notes, Stewart Jones takeaways, gaps |
| `02_roadmap_2026_05.md` | Live M0-M11 roadmap with task IDs, hours, acceptance criteria, commit-message templates. **Last revised 2026-05-15** after M0-M5 closed and a reality audit shrank M6-M11 effort from 24-33 d → ~20 d |

## Headline

1. **Qt is the only supported front-end.** Tk frozen and removed in M3 (✅ done; CI-guarded).
2. **Character Builder window matches the AccuRig HUD** (top toolbar / left rail / center viewport / right inspector / bottom strip). ✅ Shipped in M2.
3. **Four model-type modes** matching KOTOR's actual asset shapes:
   - Headless Body — **✅ DONE** (M5, PR #53)
   - Head — **🟡 next** (M6, ~4 d)
   - Supermodel (Head + Headless composite snapped at `headhook`) — M7
   - Creature — M8 (only mostly-greenfield milestone)
4. **Stewart Jones playbook** drives Creature mode: 3-Stage Asset Build, spline-IK chains, wing rig with FLAP/FOLD/LINK/CTRL layers, ROM test files. — M8
5. **Validation surfaces live** through the bottom-strip banner. — M5 partial; M9 debounces.

## Status (post-M5, 2026-05-15)

| Milestone | Status | Effort |
|-----------|--------|--------|
| M0–M5 | ✅ DONE (6 of 11) | shipped |
| M6 Head | 🟡 backend ready | ~4 d |
| M7 Supermodel | 🟡 backend ready | ~3 d |
| M8 Creature | 🔴 greenfield | ~7 d |
| M9 Live validation | 🟡 partial | ~2 d |
| M10 Export polish | 🟡 writers exist | ~2 d |
| M11 Visual regression | 🟡 infra ready | ~2 d |
| **Total remaining** | | **~20 d** |

## Critical path remaining

`M5 ✅ → M6 → M7 → M8 → M11`, with M9 + M10 ridable in parallel from M6 onwards.

Shortest path to feature-complete v7 Character Builder: **M6 → M7 → M9 → M10** (~11 dev-days). M8 + M11 ship after.

Supersedes `knowledge_base/reference/ROADMAP_legacy_2026_04.md` for the Qt branch. The older roadmap is kept for historical reference only.
