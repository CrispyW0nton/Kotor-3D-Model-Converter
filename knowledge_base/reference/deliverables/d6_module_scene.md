# Deliverable 6: Module Editor & Scene Assembly
# ================================================
# File: src/core/scene_manager.py, src/gui/main_window.py
# Priority: LOW | Effort: ~20 hours | Risk: LOW

## Problem Statement
Module loading is basic; scene manager doesn't support engine-style scene assembly.
GUI panels are not driven from domain logic.

## Tasks (from roadmap spreadsheet)
| Task | Description | Hours | Files | Acceptance |
|------|------------|-------|-------|------------|
| T701 | Scene graph from module data | 8 | scene_manager.py | Hierarchical scene from ARE/GIT/LYT |
| T702 | Domain-driven GUI panels | 6 | main_window.py | Panels observe scene model |
| T703 | Walkmesh integration | 6 | scene_manager.py | Walkmesh renders in viewport |

## Cross-Reference
- **KotOR.js**: Module loader architecture (ARE + GIT + LYT -> scene graph)
- **PyKotor**: Walkmesh resource parsing
- **Gregory Ch 8**: Game loop drives scene updates; GUI is presentation layer only

## KOTOR Module Structure
- **ARE**: Area resource (properties, ambient settings)
- **GIT**: Game Instance Table (placed objects, creatures, triggers)
- **LYT**: Layout (room positions and connections)
- **WOK**: Walkmesh (navigation mesh per room)

## Acceptance Criteria
1. Module loads all rooms from LYT with correct positions
2. Placed objects from GIT appear at correct locations
3. Walkmesh renders as overlay in viewport
4. GUI panels update reactively when scene changes
