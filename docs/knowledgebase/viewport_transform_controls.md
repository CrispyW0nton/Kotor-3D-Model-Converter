# Viewport Transform Controls

GhostRigger's main viewport has additive 3ds Max-inspired transform controls for KMAX scene objects: an Axis / Reference Coordinate System dropdown in the viewport toolbar and a dockable Adjust Pivot toolbox.

## Adjust Pivot

Each `SceneObjectInstance` owns persistent `pivot` data next to its `transform`. Missing pivot blocks in older `.kmax` files load as object-origin pivots.

- `Affect Pivot Only` moves or rotates the selected object's pivot without moving the visible object.
- `Affect Object Only` transforms the object around the current pivot.
- `Affect Hierarchy Only` is reserved for group/hierarchy transforms. It is disabled unless the selection exposes hierarchy/group data.
- `Center to Object` sets each selected object's pivot position to the local bounding-box center.
- `Align to Object` aligns pivot orientation to the object orientation.
- `Align to World` resets pivot axes to world orientation while preserving pivot position.
- `Reset Pivot` returns the pivot to local origin and identity rotation.

Locked objects disable pivot actions. Objects without bounds cannot use Center to Object.

## Axis Modes

Axis modes are centralized in `src/core/scene/axis_mode.py`:

- `World`: global axes.
- `Local`: selected object/pivot orientation.
- `Parent`: parent/group orientation, falling back to World.
- `View`: active camera basis.
- `Screen`: first-pass View-equivalent orientation for screen-plane transforms.
- `Gimbal`: first-pass Local-equivalent basis with a future Euler/gimbal extension point.
- `Grid`: world-grid basis until custom grids/workplanes exist.
- `Working`: user-defined working basis when available, falling back to World.
- `Pick`: uses another clicked object's local axes as the transform reference.

`TransformReferenceController` stores the active mode, resolves picked references, clears invalid picks, and provides the basis consumed by the gizmo.

## Pick Reference Workflow

Choosing Pick shows: `Pick an object to use as transform reference.` The next viewport object click stores that object as the reference and the gizmo uses its local axes. `Esc` cancels pick mode. Clicking empty space keeps the viewport waiting and does not permanently alter normal selection.

## KMAX Persistence

Pivots serialize per object:

```json
"pivot": {
  "position_local": [0.0, 0.0, 0.0],
  "rotation_local": [0.0, 0.0, 0.0],
  "enabled": true,
  "metadata": {}
}
```

Temporary UI pick state is not saved in `.kmax`. App settings remember the last axis mode, Adjust Pivot dock visibility, and last pivot edit mode.

## Gizmo Integration

The existing transform gizmo is reused. Scene wrapper nodes receive runtime pivot origin, pivot orientation, pivot edit mode, and axis-basis metadata before draw/drag. Translation moves the object normally in Affect Object mode and moves only pivot metadata in Affect Pivot mode. Rotation and scale use the pivot as the operation center where supported.

Known limitations: hierarchy mode has structural hooks but no synthetic hierarchy behavior; Screen is View-equivalent for first pass; Gimbal and Working fall back to local/world behavior until dedicated Euler/workplane systems are expanded.
