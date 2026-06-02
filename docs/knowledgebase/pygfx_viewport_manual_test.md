# pygfx Viewport Manual Test

Use this checklist after changing the optional pygfx viewport backend.

1. Launch GhostRigger from the repository root with `python main.py`.
2. Open Settings and switch the viewport renderer to `pygfx / WGPU`.
3. Confirm the status/log diagnostics report `pygfx_wgpu`, the WGPU backend preference, and adapter details when available.
4. Load a model.
5. Orbit the camera and confirm the scene remains responsive without mesh rebuild diagnostics increasing on camera-only frames.
6. Pan the camera and confirm no model reload or geometry recreation occurs.
7. Zoom the camera and confirm FPS/frame-time diagnostics remain stable.
8. Select an object and confirm highlighting changes without geometry rebuild diagnostics increasing.
9. Move the selected object with the translate/rotate/scale gizmo and confirm the gizmo follows the object.
10. Switch back to the existing WGPU or ModernGL renderer and confirm the old viewport backend still renders.
11. Temporarily run without pygfx installed, or simulate the missing dependency in a clean environment, and confirm GhostRigger launches with a fallback renderer and a clear diagnostic.
