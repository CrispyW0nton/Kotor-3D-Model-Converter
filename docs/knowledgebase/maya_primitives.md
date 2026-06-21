# Maya Polygon Primitive Reference for Map Studio

Date captured: 2026-06-21  
Tool: Autodesk Maya 2025 `mayapy.exe`  
Exporter: `tools/maya/export_maya_polygon_primitives.py`  
Fixture directory: `docs/knowledgebase/maya_primitives/maya2025/`

## Purpose

These fixtures are a ground-truth reference for Map Studio's primitive creation tools. They were exported directly from Maya so GhostRigger can match familiar DCC behavior where it helps modders, and deliberately diverge where KOTOR module authoring needs safer geometry, WOK generation, or lower runtime complexity.

This reference is polygon-only. NURBS primitives are not targeted for Map Studio runtime geometry because KOTOR module output requires compiled mesh/walkmesh resources.

## Captured Primitive Set

| Primitive | Maya command | Vertices | Edges | Faces | Triangles | Bounds size |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Cube | `polyCube` | 8 | 12 | 6 | 12 | `1.000 x 1.000 x 1.000` |
| Sphere | `polySphere` | 114 | 240 | 128 | 224 | `1.000 x 1.000 x 1.000` |
| Cylinder | `polyCylinder` | 34 | 80 | 48 | 64 | `1.000 x 1.000 x 1.000` |
| Cone | `polyCone` | 17 | 32 | 17 | 30 | `1.000 x 1.000 x 1.000` |
| Torus | `polyTorus` | 128 | 256 | 128 | 256 | `0.940 x 0.240 x 0.940` |
| Plane | `polyPlane` | 4 | 4 | 1 | 2 | `1.000 x 0.000 x 1.000` |
| Platonic Solid | `polyPlatonicSolid` | 20 | 30 | 12 | 36 | `0.934 x 0.934 x 0.934` |
| Pyramid | `polyPyramid` | 5 | 8 | 5 | 6 | `1.414 x 0.707 x 1.414` |
| Prism | `polyPrism` | 26 | 51 | 27 | 48 | `0.866 x 1.000 x 1.000` |
| Pipe | `polyPipe` | 64 | 128 | 64 | 128 | `1.000 x 0.500 x 1.000` |
| Helix | `polyHelix` | 272 | 528 | 258 | 540 | `1.300 x 1.700 x 1.300` |

Unavailable or excluded from this Maya 2025 command set:

- `polyDisc`, `polySoccerBall`, `polySuperShape`, and `polyGear` were not available through default `maya.cmds`.
- `polyPrimitive` exists but is a generic/internal constructor, not a distinct user-facing primitive.

## Map Studio Implications

Current GhostRigger primitive coverage already includes floor/plane, wall, cube, cylinder, ramp, stairs, doorway frame, and arch. The Maya pass shows the next parity targets for a Maya-like tool belt:

- `sphere`: useful for gameplay marker visualization and rounded blockouts, but should default to low segment counts for KOTOR module performance.
- `cone`: useful for marker/debug volumes, roof forms, spikes, and quick visual guides.
- `torus`: useful for rings, arches, circular trim, or sci-fi detail, but should be opt-in because it is dense by default.
- `pyramid`: useful for roofs, low-poly props, marker volumes, and temple-like forms.
- `prism`: useful for wedge/corner forms and triangular structural pieces.
- `pipe`: useful for columns, vents, tunnels, circular door frames, and corridor detail.
- `helix`: useful as a reference for advanced modeling only; it is too dense for a default KOTOR map primitive.
- `platonic_solid`: useful mostly for debug/marker primitives, not core map layout.

## Coordinate Notes

Maya exports these primitives in a Y-up world with centimeter units. GhostRigger Map Studio must keep KOTOR/viewport conventions explicit when importing or recreating them.

Important observed behavior:

- Maya `polyPlane` lies flat in the XZ plane with zero Y height. If Map Studio uses Z-up authored room geometry, the plane must be converted or generated natively as an XY floor with Z elevation.
- Maya cylinder, cone, pipe, torus, and helix axis defaults are centered around Maya Y. Map Studio should offer axis/orientation options instead of baking Maya's Y-up axis into KOTOR room builders.
- Maya primitives often include quads/ngons. MDL/WOK export should triangulate deterministically at compile time and keep the editable primitive intent intact in KMAP.

## Implementation Guidance

When adding Map Studio primitive parity:

1. Put primitive intent and mesh builders in the headless module layer, not the UI.
2. Preserve editable parameters in KMAP: radius, height, segments, axis, cap mode, hollow thickness, and transform.
3. Generate deterministic triangles for export while keeping editor meshes readable.
4. Mark MDL/MDX/WOK/LYT/VIS/PTH outputs stale after any primitive create/edit/delete.
5. Use WOK only for walkable primitives, such as floors, ramps, terrain, and stairs. Decorative primitives should not generate WOK faces by default.
6. Keep Maya parity as a UX reference, not a runtime mandate. KOTOR-safe defaults should win when topology density or orientation differs.

## Regeneration

Run:

```powershell
& "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" `
  tools\maya\export_maya_polygon_primitives.py `
  --output docs\knowledgebase\maya_primitives\maya2025
```

The exporter writes individual `.fbx`, `.ma`, `.obj`, and `.json` files plus `maya_polygon_primitives_manifest.json`.
