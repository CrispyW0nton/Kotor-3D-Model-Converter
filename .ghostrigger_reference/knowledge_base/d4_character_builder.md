# Deliverable 4: Character Builder
# ==================================
# File: src/gui/character_builder_window.py (new/refactor)
# Priority: MEDIUM | Effort: ~43 hours | Risk: MEDIUM

## Problem Statement
Character Builder is currently a panel inside main_window.py, not a dedicated workspace.
It lacks a GPU viewport, guided workflow, validation, and proper rig transfer tools.

## Required Redesign (from character_builder_spec.md)
Create a dedicated workspace with:
1. Large left GPU viewport (3D preview)
2. Tall right control panel with mode tabs
3. Five workflow modes: Assembly, Rig, Face, Preview, Export
4. Searchable part library (heads, bodies, equipment)
5. Template-guided KOTOR rig transfer
6. Continuous validation (hooks, weights, supermodel refs)

## Tasks (from roadmap spreadsheet)
| Task | Description | Hours | Files | Acceptance |
|------|------------|-------|-------|------------|
| T501 | New CharacterBuilder window | 8 | character_builder_window.py | Opens as dedicated workspace |
| T502 | Workflow navigation (5 modes) | 6 | character_builder_window.py | Tab switching works |
| T503 | Part library browser | 6 | character_builder_window.py | Search/filter by type |
| T504 | Head-hook snapping | 4 | character_builder_window.py | Head snaps to body hook |
| T505 | Symmetry-aware rigging | 6 | auto_rigger.py | Mirror weights L<->R |
| T506 | Camera presets | 3 | character_builder_window.py | Front/side/back buttons |
| T507 | Facial preview | 4 | character_builder_window.py | LIP animation preview |
| T508 | Validation panel | 6 | character_builder_window.py | Real-time weight/hook checks |

## Cross-Reference
- **KotorBlender** (`io_scene_kotor/`): Head/body hook system, armature transfer
- **PyKotor** (`resource/`): KOTOR resource enumeration for part library
- **Mukundan Ch 7.7**: Animation retargeting for rig transfer
- **Gregory Ch 7.2**: Resource manager pattern for part library caching

## KOTOR-Specific Requirements
- **Head hooks**: Body models have `headhook` node; head model root attaches there
- **Supermodel**: Character models reference `s_female01` or `s_male01` for base animations
- **Body slots**: K1 uses `PFBA`, `PFBB`, etc.; K2 uses different naming
- **Weight groups**: Must match KOTOR bone names exactly (head, torso, l_arm, r_arm, etc.)

## Acceptance Criteria
1. Dedicated window opens from main menu
2. Five workflow modes accessible via tabs
3. Part library lists available heads/bodies from game data
4. Head snaps to body's headhook node correctly
5. Symmetry rigging mirrors weights accurately
6. Validation catches missing hooks, bad weights, wrong supermodel
7. Export produces valid KOTOR MDL/MDX pair
