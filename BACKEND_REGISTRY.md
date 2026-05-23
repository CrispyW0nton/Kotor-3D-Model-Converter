# FBX Backend Registry

## Current Status

- Production backend: Blender 4.2 headless, verified locally.
- Secondary backend: Autodesk FBX SDK, optional, not installed in the current shell environment.
- Retarget Workbench animation import path: FBX -> Blender headless -> sampled JSON -> SourceSkeletonClip.
- Legacy generic mesh import path: pyassimp -> assimp_py -> trimesh, not used for Retarget Workbench animation import.

## Blender Headless Backend (Production Default)

- Executable: `C:\Program Files\Blender Foundation\Blender 4.2\blender.exe`
- Version verified locally: `Blender 4.2.0`
- Build date verified locally: `2024-07-16`
- Import operator: `bpy.ops.import_scene.fbx`
- Export operator: `bpy.ops.export_scene.fbx`
- Export formats in GhostRigger: `FBX201600` by default, `FBX202000` optional.
- Pipeline: FBX -> Blender headless -> sampled JSON -> SourceSkeletonClip.
- Selection: default backend when no override is configured.

## Autodesk FBX SDK Backend (Optional Secondary)

Official source: https://aps.autodesk.com/developer/overview/fbx-sdk

The Autodesk FBX SDK is a manually installed local dependency. Do not commit,
vendor, or redistribute Autodesk SDK installers, headers, DLLs, Python bindings,
`.pyd` files, extracted SDK trees, or generated SDK packages in this repository.
The GhostRigger repo may contain detection code, documentation, tests using fake
SDK modules, and adapter interfaces only.

Installation status:

- [x] Not installed in current shell environment.
- [ ] Installed.
- [ ] Verified.

### Installation Requirements

1. SDK version: Autodesk FBX SDK 2020.3.4 or later.
2. Python runtime: install bindings for the exact Python executable used by GhostRigger.
3. Binding install: `pip install fbx-python-sdk`, or an SDK-provided wheel/package compatible with the active interpreter.
4. Architecture: Windows x64.

Important runtime note:

- Current shell verification on 2026-05-23 used `C:\Python314\python.exe`.
- Current shell Python version: `3.14.0`.
- `import fbx` failed in that shell: `ModuleNotFoundError: No module named 'fbx'`.
- The Qt application runtime was reported as Python 3.13. Verify Autodesk bindings in that same runtime before enabling SDK-backed UI choices.

### Post-Installation Verification

Run this in the same Python environment that launches GhostRigger:

```bash
python -c "import sys; print(sys.version); print(sys.executable); import fbx; manager = fbx.FbxManager.Create(); print(f'SDK Version: {manager.GetVersion()}'); manager.Destroy()"
```

Expected result:

- The `fbx` module imports successfully.
- `fbx.FbxManager.Create()` returns a manager.
- The SDK version is printed.

### Installation Record

- SDK version installed: PENDING.
- Python environment used: PENDING.
- Installation date: PENDING.
- Verification status: PENDING.

## Backend Selection Configuration

- Default: Blender headless.
- Override: set `FBX_BACKEND=autodesk_sdk` in the environment.
- Fallback: if Autodesk SDK is requested but unavailable, the backend factory falls back to Blender unless fallback is explicitly disabled.

## Development Rules

- Keep `src/core/retargeting/fbx_importer.py` as the stable production animation importer.
- Keep `src/core/retargeting/blender_animation_injection.py` and `scripts/blender_extract_ue5_animation.py` as the stable Blender extraction bridge.
- Keep `src/core/retargeting/fbx_exporter.py` as the stable Blender export path.
- Do not route Retarget Workbench animation imports through `src/converters/mesh_converter.py`.
- Add Autodesk SDK parsing only behind `src/core/retargeting/fbx_backend.py` and prove it emits the same `SourceSkeletonClip` contract before using it in product UI.
