# GhostRigger - KotOR 1 & 2 Modding Suite

GhostRigger is a Qt/PySide6 desktop suite for inspecting, previewing, editing,
retargeting, and exporting *Star Wars: Knights of the Old Republic* and *The
Sith Lords* 3D resources.

The active development line is:

```text
qt-ghostrigger
```

Older non-Qt branches are preserved only as legacy history. New work should be
based on `qt-ghostrigger`.

GhostRigger is not affiliated with LucasArts, BioWare, Obsidian, Disney,
Aspyr, or Autodesk. KotOR game assets and the Autodesk FBX SDK are not bundled.

## Current Capability Status

| Area | Status |
| --- | --- |
| Main Viewport / KMAX Scene Editor | Active Qt scene workflow with model import, cameras, lights, pivots, transform tools, themes, and `.kmax` scene files. |
| Resource Browser | Active K1/K2 game-library browser for models, modules, textures, resources, and categorized content. |
| Animation Retargeting Workbench | Active product flow for Unreal/Mixamo/FBX to KotOR, KotOR to KotOR, and initial KotOR to Unreal backend contracts. Blender FBX and Autodesk SDK are separate backend options. |
| Character Builder | In active development. Base-skeleton selection, external mesh import, fit/orientation helpers, native skeleton build flow, supermodel assignment, BAS preview attachments, and export preflight are being hardened. Treat exported characters as candidates until in-game verified. |
| Body Attachment System | Active preview/build system for head, weapon, mask, goggle, belt, and equipment socket layers. |
| Lightsabers | Active viewport support for animated blade planes, game-color blade previews, and preview-only blade color overrides. |
| Module / Map Tooling | KMAP/KMAX foundations exist. Module authoring remains staged and should preserve source game data until an explicit export/write operation. |

## Requirements

Recommended Windows development/runtime:

- Windows 10 or newer
- Python 3.13 preferred for the current Qt branch, Python 3.12 also supported
- A legal local installation of KotOR and/or TSL
- Blender 4.2 LTS if using the Blender FBX backend
- Optional Autodesk FBX SDK installed manually if using Autodesk SDK FBX paths

Install Python dependencies from:

```bat
pip install -r requirements.txt
```

The project uses Qt through PySide6. The old Tk UI was removed and should not be
reintroduced.

## Build A Windows Exe

Use:

```bat
build.bat
```

The script:

1. Resolves Python from `GHOSTRIGGER_PYTHON`, `py -3.13`, `py -3.12`, or `python`.
2. Installs `requirements.txt`.
3. Installs PyInstaller hook helpers.
4. Attempts optional generic FBX packages for legacy main-viewport FBX import.
5. Compiles build-critical entry points.
6. Runs:

```bat
python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm
```

Successful output:

```text
dist\GhostRigger-K1-K2.exe
```

All build output is written to `build_log.txt`.

Autodesk FBX SDK is not installed or bundled by `build.bat`. Install it manually
from Autodesk and configure the matching Python bindings for your Python
runtime.

## Run From Source

```bat
git clone https://github.com/CrispyW0nton/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
git switch qt-ghostrigger
pip install -r requirements.txt
python main.py
```

On first launch, configure game paths in the Settings/Game Paths area. The
library browser will then index game resources from KEY/BIF/RIM/ERF/MOD and
Override layers.

## First Launch Workflow

1. Start GhostRigger.
2. Set K1 and/or K2 install paths.
3. Scan or refresh the game library.
4. Load a model from the Content Browser.
5. Use the viewport display controls for bones, textures, lights, helpers,
   cameras, gizmos, measurement, and render backend diagnostics.
6. Save editor scenes as `.kmax` when arranging multiple scene objects.

GhostRigger scene formats intentionally store references and lightweight editor
state. They should not embed large proprietary KOTOR asset bytes.

## Main Viewport And KMAX

The main viewport is a scene editor, not a single-model-only viewer.

Use it for:

- Loading and comparing K1/K2 models
- Inspecting MDL/MDX hierarchy, textures, lights, cameras, helpers, and skins
- Transforming scene objects
- Editing pivots and freezing transforms
- Authoring cameras/lights and sequence data
- Saving `.kmax` scenes

Workflow-specific controls belong in their owning workbench. Retarget mode,
source animation choices, target output naming, and retarget export controls
belong in the Animation Retargeting Workbench, not the main viewport.

## Animation Retargeting Workbench

Open the Animation Retargeting Workbench when your task is animation transfer.

Supported product flows:

- Unreal/Mixamo/FBX animation source to KotOR target model
- KotOR source animation to KotOR target model
- Initial KotOR source animation to Unreal target skeleton pipeline

Typical Unreal/Mixamo to KotOR workflow:

1. Choose `Unreal -> KOTOR`.
2. Import an external FBX animation source, or choose a source from the game
   library where appropriate.
3. Load a KotOR target model such as `pmbam`.
4. Pick the source animation row.
5. Set the target output per animation:
   - Vanilla slot override
   - Custom animation patch
6. Press Retarget to preview the result on the target model.
7. Use Play/Pause/Stop to inspect both source and target playback.
8. Export MDL/MDX only after preview/readback gates pass.

Important terms:

- Source animation: the animation being sampled.
- Target output animation: the name attached to the exported KotOR model.
- Vanilla slot override: uses an existing KotOR animation slot.
- Custom animation patch: writes a custom local animation name and requires a
  runtime/patch workflow to play in-game.

## FBX Backends

GhostRigger keeps FBX backends explicit.

| Backend | Use | Notes |
| --- | --- | --- |
| Blender Headless | Production Blender FBX import/export bridge for animation and mesh extraction. | Requires Blender 4.2 LTS or `GHOSTRIGGER_BLENDER_PATH`. |
| Autodesk FBX SDK | Optional SDK-backed path. | Must be installed manually due Autodesk licensing. No SDK binaries are committed or bundled. |
| Generic Assimp paths | Legacy/static mesh import support. | Useful for some main-viewport file imports, not a replacement for the Retarget Workbench animation backend. |

Autodesk SDK setup:

1. Download the SDK from [Autodesk FBX SDK](https://aps.autodesk.com/developer/overview/fbx-sdk).
2. Install a Windows x64 SDK version compatible with your Python runtime.
3. Install or expose the matching Python `fbx` bindings.
4. Verify:

```bat
python -c "import fbx; m=fbx.FbxManager.Create(); print(m.GetVersion()); m.Destroy()"
```

Blender is not treated as a silent fallback for Autodesk SDK requests. If a
workflow asks for Autodesk and the SDK is missing, GhostRigger should fail with
an actionable setup message unless that workflow explicitly opts into a
fallback.

## Character Builder

Character Builder is the custom-character pipeline. It is not launch-complete
yet, but the intended modder workflow is:

1. Choose a base KotOR model/skeleton.
2. Load a custom mesh, currently FBX/OBJ-oriented.
3. Auto-fit the custom mesh to the selected KotOR skeleton using skeleton
   landmarks, front-axis detection, scale normalization, and KOTOR reference
   bounds.
4. Fine-tune bones and mesh fit manually.
5. Build/confirm the native KotOR node hierarchy and bind rows.
6. Assign a supermodel or local animation slots.
7. Preview heads, weapons, masks, goggles, belts, and attachments through the
   Body Attachment System socket layer.
8. Run validation/export preflight.
9. Export MDL/MDX candidates and in-game test.

The Character Builder must preserve KotOR-specific concepts:

- Exact node names and casing
- Supermodel inheritance
- MDL/MDX pairing
- Skin bonemaps/qbones/tbones
- Attachment sockets such as `headhook`, `rhand`, `lhand`, `MaskHook`,
  `GoggleHook`, and `pelvis_g`

Do not claim a custom character is game-ready until viewport preview, export
readback, and in-game testing have passed.

## Body Attachment System

The Body Attachment System previews and saves socket-following attachment
recipes. It treats heads, weapons, masks, goggles, and belts as attachment
layers that follow animated body sockets without entering the body skinning
palette.

Use BAS for:

- Headless body previews
- Weapon and equipment socket checks
- Full-body equipment previews
- Character Builder preview-tab attachment checks

## Lightsaber Preview

Lightsaber models use special blade plane/material behavior in KotOR. GhostRigger
adds preview support for:

- Powered/off/powerup/powerdown blade animation playback
- Procedural game-colored blade textures when stock blade masks are not useful
- Preview-only blade color selection for lightsaber models
- Emissive-looking viewport presentation

The color picker should appear only for lightsaber models.

## Module And Map Workflows

Module and map work belongs in Module Studio/Map Studio/KMAP surfaces.

- **Module Studio** is for existing KOTOR module/resource editing: hydrate RIM/MOD
  data, inspect ARE/GIT/IFO/templates/WOK resources, edit fields safely, and save
  with backups/manifests.
- **Map Studio** is for authored/custom module creation: build room and terrain
  geometry from primitives, floor-plan operations, terrain heightfields/sculpt
  tools, generate WOK/PTH/LYT/VIS, place gameplay objects, and package a staged
  `.mod` that can be copied into the game.
- `.kmap` stores module/room/resource references and lightweight overrides.
- `.kmax` stores scene objects, transforms, cameras, lights, pivots, and editor
  scene state.
- Source KOTOR data should not be modified unless the user explicitly chooses
  an export/write operation.

The current first Map Studio proof target is `grdev01`: a generated KOTOR 1
dev-test module with authored room MDL/MDX/WOK, ARE/GIT/IFO/PTH/LYT/VIS,
player start, one test placeable, staged `.mod`, and a required in-game
`warp grdev01` screenshot/video proof before it can be called game-tested.

## Validation And Export Safety

Shared architecture foundations:

- `GhostRiggerProject`
- `ResourceAddress`
- `ValidationBus`
- `ExportJob`

Export flows should:

1. Run validation/preflight before writing.
2. Stage output files.
3. Verify staged outputs.
4. Promote files only after verification.
5. Avoid partial writes.
6. Report actionable issues.

## Testing And Verification

Prefer targeted checks:

```bat
python -m py_compile main.py src\core\retargeting\fbx_backend.py
python -m pytest tests/test_fbx_backend_registry.py -q
python -m pytest tests/test_character_builder_template_rig.py -q
python -m pytest tests/test_headless_body_workflow.py -q -k "external_model_normalization or generated_rom"
```

For UI, startup, viewport, theme/layout, or workflow changes, visible testing in
the real GhostRigger app is required. Backend MCP tools are for model-pipeline
truth checks, not a substitute for visual UI testing.

Do not run broad full scans unless the task explicitly requires it.

## Roadmap Pointers

Roadmap and knowledge-base material lives under:

```text
knowledge_base/roadmap/
knowledge_base/reference/
knowledge_base/retargeting/
docs/
```

Current development priorities:

- Stabilize Character Builder auto-fit, skeleton build, supermodel preview, and
  MDL/MDX export preflight.
- Continue improving Mixamo/UE to KotOR retarget quality without weakening the
  verified export gates.
- Keep Retarget, Character, Module, Map, BAS, and main viewport UI boundaries
  separate.
- Keep the Qt branch as the primary branch and preserve older branches as
  legacy references.

## Git And Branch Policy

- Primary branch: `qt-ghostrigger`
- Legacy branches: keep old branches available for history; do not base new
  feature work there.
- Commit messages should include the relevant roadmap task ID when applicable.
- Open future PRs against `qt-ghostrigger`.
