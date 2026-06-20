# Vertex Skill

Use this before changing vertex, edge, face, snap, weld, selection, or component
editing behavior in Map Studio or Character Builder.

Sources: Mukundan mesh processing, de Berg computational geometry, Dunn/Parberry
geometric primitives/tests, Vince transforms, O'Hailey rigging workflows.

## Working Rules

- Component editing must be undoable and scoped: Object, Vertex, Edge, Face, and
  Walkmesh are different edit modes with different validation risks.
- Vertex snapping is not welding. Snap moves one component to a target; weld
  merges topology and must update faces/WOK references.
- Preserve selection intent across edits where possible. Avoid silently clearing
  selection after every operation unless topology invalidates it.
- Reject degenerate output early: duplicate points, zero-length edges,
  zero-area faces, inverted WOK triangles, and collapsed doorway seams.
- Support Maya-style point snapping as a user gesture, but route it through
  domain operations so KMAP, WOK, and readiness state update together.
- For Character Builder bones, moving guide joints must not mutate the imported
  mesh payload transform unless the operation explicitly binds/freezes.

## GhostRigger Applications

- Hold-V vertex/bone snapping should identify nearby valid snap targets and
  apply one undoable move command.
- Symmetry must be a toggleable policy, not a hidden side effect. Mirrored edits
  should be explicit in command metadata.
- Vertex edits in Map Studio should mark staged exports/game proof stale.
- Component mode labels in UI should match the actual active edit scope.

## Preflight Checklist

- What component type is active?
- What exact item(s) are selected?
- Does the operation mutate transform, topology, WOK intent, or selection?
- Does the operation preserve stable KMAP IDs?
- Is the output still valid for MDL/WOK generation?
- Is undo/redo possible for destructive edits?

## Tests To Prefer

- Snap source vertex to target vertex across rooms.
- Weld selected vertices and assert face indices are repaired.
- Flatten vertices on X/Y without invalidating footprint.
- Symmetry on/off tests for paired guide/bone moves.
