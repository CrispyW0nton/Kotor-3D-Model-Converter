# Roadmap 2026-05 — Qt Character Builder Re-design

This folder contains the post-Qt-migration roadmap for GhostRigger, derived from:

- Reallusion AccuRig HUD reference (user-supplied screenshot + video `e9AMHU_Dgf0`)
- Facial rigging tutorial (`pLRxzsPAqrE`)
- Stewart Jones, *Digital Creature Rigging: Wings, Tails & Tentacles* (CRC Press, 2019)
- A full audit of the `qt-ghostrigger` branch (last refreshed 2026-05-16, post-M6 launch-gap audit)
- The pre-existing `knowledge_base/reference/specs/character_builder_spec.md`

## Files

| File | Purpose |
|------|---------|
| `01_qt_branch_audit.md` | Audit of the current Qt branch: Tk-vs-Qt status, module map, KOTOR model-type taxonomy, HUD design notes, Stewart Jones takeaways, gaps |
| `02_roadmap_2026_05.md` | Live launch roadmap with task IDs, hours, acceptance criteria, commit-message templates. **Last revised 2026-05-16** after M12/M10 local Character Builder launch work plus the broader product-pillar audit for Unity MCP transfer, Asset Viewer, Module Editor, and Map Builder |

## Headline

1. **Qt is the only supported front-end.** Tk frozen and removed in M3 (✅ done; CI-guarded).
2. **Character Builder window matches the AccuRig HUD** (top toolbar / left rail / center viewport / right inspector / bottom strip). ✅ Shipped in M2.
3. **Four model-type modes** matching KOTOR's actual asset shapes:
   - Headless Body — **✅ DONE** (M5, PR #53)
   - Head — **✅ DONE** (M6, PR #54)
   - Supermodel (Head + Headless composite snapped at `headhook`) — M7 partial
   - Creature — M8 (only mostly-greenfield milestone)
4. **Stewart Jones playbook** drives Creature mode: 3-Stage Asset Build, spline-IK chains, wing rig with FLAP/FOLD/LINK/CTRL layers, ROM test files. — M8
5. **Validation surfaces live** through the bottom-strip banner. — M5 partial; M9 debounces.
6. **Unity/MCP transfer, Asset Viewer, Module Editor, and Map Builder** now have explicit milestone gates instead of being treated as vague future work.

## Status (post-M12 launch-proof update, 2026-05-16)

| Milestone | Status | Effort |
|-----------|--------|--------|
| M0–M6 | ✅ DONE (7 of 12) | shipped |
| M7 Supermodel | 🟡 partial | ~3 d |
| M8 Creature | 🔴 greenfield | ~7 d |
| M9 Live validation | 🟡 partial | ~2 d |
| M10 Export polish | ✅ done locally | awaiting review/PR |
| M12 External Mesh Launch Path | ✅ done locally | awaiting review/PR |
| M11 Visual regression | 🟡 infra ready | ~2 d |
| M13 Unity MCP transfer | 🟡 started | ~4 d |
| M14 Asset Viewer | ✅ done locally | awaiting review/PR |
| M15 Module Editor | 🟡 started | T1501-T1503 done locally |
| M16 Map Builder | 🔴 gap | ~8 d |
| **Character Builder launch remaining** | | **~8 d** |
| **Full suite foundation remaining** | | **~33 d** |

## Critical path remaining

`M13 → M14 → M9 → M11`, with M8 Creature work deferred until the humanoid/head pipeline polish is locked.

Shortest path to feature-complete v7 Character Builder: **M9**, then M11 regression lock-in. A public modder beta also needs M13/M14 so exported characters can be transferred and previewed outside the game. M8 ships after unless Creature is explicitly prioritized.

Supersedes `knowledge_base/reference/ROADMAP_legacy_2026_04.md` for the Qt branch. The older roadmap is kept for historical reference only.
