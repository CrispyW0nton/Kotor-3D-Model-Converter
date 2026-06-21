<p align="center">
  <img src="assets/icons/ghostrigger_icon.png" alt="GhostRigger application icon" width="128">
</p>

# GhostRigger

**A KOTOR 1 and KOTOR 2 modding suite for model inspection, animation
retargeting, character building, module editing, map authoring, and safe
export workflows.**

GhostRigger is a hybrid Visual Studio C++ host plus embedded Python Qt/PySide6
desktop application. It is built for *Star Wars: Knights of the Old Republic*
and *The Sith Lords* modding workflows, with a strong bias toward preserving
source game data, validating outputs, and keeping user-facing tools separated
from reusable core systems.

The active development branch is `qt-ghostrigger`.

GhostRigger is not affiliated with LucasArts, BioWare, Obsidian, Disney, Aspyr,
or Autodesk. KOTOR game assets and Autodesk FBX SDK binaries are not bundled.

## What It Is

GhostRigger is organized as four authoring studios over shared project,
resource, validation, export, scene, and native-runtime foundations.

| Studio | Purpose | Current Status |
|--------|---------|----------------|
| Character Studio | Import custom FBX/OBJ/glTF meshes, fit them to native KOTOR model hierarchies, bind/skin, preview animations and attachments, and export MDL/MDX candidates. | Active development. The main launch risk is exact Odyssey node-DAG preservation and golden playable exports. |
| Retarget Studio | Retarget animations between Unreal/Mixamo/FBX and KOTOR, KOTOR to KOTOR, and KOTOR to Unreal. | Advanced partial. Unreal/Mixamo to KOTOR is strongest; the other lanes are being brought up to the same preview/export/readback standard. |
| Module Studio | Hydrate, inspect, edit, validate, and safely save existing KOTOR modules and resources. | Backend services exist for hydration, GFF object forms, WOK editing, save manifests, and reference checks; visible editing and undo remain active work. |
| Map Studio | Author custom KMAP/KMAX-backed areas, rooms, terrain, LYT/VIS/WOK, gameplay placements, package output, and game-test proof. | Backend/product foundations exist. Visible workflow consolidation and real `grdev01` in-game proof remain active work. |

Shared foundations already in the repository include `GhostRiggerProject`,
`ResourceAddress`, `GameResourceProvider`, `ValidationBus`, `ExportJob`,
provider-backed resource models, native package boundaries, and embedded Python
payload generation.

## Highlights

- Qt-only desktop UI; the legacy Tk UI is retired.
- Scene-based main viewport with KMAX scene files, cameras, lights, pivots,
  transforms, gizmos, measurements, render diagnostics, and multi-object state.
- Game-library and resource browsing for K1/K2 KEY/BIF/RIM/ERF/MOD/Override
  layers.
- Retarget workbench with explicit source/target/output concepts and staged
  export gates.
- Character Builder with base skeleton selection, external mesh fit helpers,
  native skeleton build flow, supermodel assignment, BAS attachment preview,
  validation, and export preflight.
- Body Attachment System for head, weapon, mask, goggle, belt, and equipment
  socket preview recipes.
- Lightsaber preview support for powered blade animation, game-color blade
  textures, and preview-only color overrides.
- Module and Map foundations for safe `.kmap`, `.kmax`, `.mod`, WOK, LYT, VIS,
  ARE, GIT, IFO, and package workflows.
- Native Visual Studio package tree with canonical owners under
  `native/GhostRigger.*`.

## Current Critical Path

The active roadmap is
[`knowledge_base/roadmap/02_roadmap_2026_05.md`](knowledge_base/roadmap/02_roadmap_2026_05.md).
Despite the filename, it was regenerated on 2026-06-21 and is the current suite
roadmap.

Near-term priorities:

1. Build the unified `ValidationBus` issue panel and navigation hooks.
2. Add shared undo-command and cancellable job/progress foundations.
3. Document and test the KMAX/KMAP/LYT/MDL/WOK transform contract.
4. Lock Character Studio native KOTOR DAG snapshot and clone-before-bind flow.
5. Bring KOTOR-to-KOTOR and KOTOR-to-Unreal Retarget Studio lanes up to the
   same preview/export/readback discipline as Unreal/Mixamo-to-KOTOR.
6. Finish real `grdev01` Map Studio game proof with recorded evidence.

## Requirements

Recommended Windows development/runtime:

- Windows 10 or newer.
- Python 3.13 preferred; Python 3.12 is also supported for the Qt branch.
- Visual Studio 2022 / MSBuild for native package work.
- A legal local installation of KOTOR and/or TSL.
- Blender 4.2 LTS for the production Blender FBX backend.
- Optional Autodesk FBX SDK installed manually for SDK-backed FBX workflows.

Install Python dependencies:

```bat
pip install -r requirements.txt
```

## Quick Start

```bat
git clone https://github.com/LordVaderCW/Kotor-3D-Model-Converter.git
cd Kotor-3D-Model-Converter
git switch qt-ghostrigger
pip install -r requirements.txt
python main.py
```

On first launch:

1. Open Settings / Game Paths.
2. Configure K1 and/or K2 install paths.
3. Scan or refresh the game library.
4. Load a model from the Content Browser.
5. Save multi-object editor scenes as `.kmax`.

GhostRigger scene files store references and lightweight editor state. They
should not embed large proprietary KOTOR asset bytes.

## Building

### PyInstaller App Bundle

```bat
build.bat
```

`build.bat` resolves Python, installs `requirements.txt`, installs PyInstaller
hook helpers, compiles build-critical entry points, and runs:

```bat
python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm
```

Successful output:

```text
dist\GhostRigger-K1-K2.exe
```

Build output is written to `build_log.txt`.

### Native Solution

Native work lives in `GhostRigger.sln` and `native/GhostRigger.*`.

- Use Visual Studio for normal Debug/Release native package work.
- Keep package ownership aligned with
  [`knowledge_base/package_ownership_model.md`](knowledge_base/package_ownership_model.md).
- Edit canonical Python under root `src/...` first when a matching source file
  exists.
- Regenerate embedded Python payload copies after canonical packaged Python
  changes.
- Do not hand-edit `native/<Project>/Python/src/...` copies to diverge from
  root source.

## Main Workflows

### Main Viewport And KMAX

The main viewport is a scene editor, not a single-model viewer.

Use it for loading and comparing K1/K2 models, inspecting MDL/MDX hierarchies,
previewing textures/lights/cameras/helpers/skins, transforming scene objects,
editing pivots, authoring cameras/lights, and saving `.kmax` scenes.

Workflow-specific controls belong in their owning workbench. Retarget mode,
source animation choices, output naming, and retarget export controls belong in
Retarget Studio, not the main viewport chrome.

### Retarget Studio

Supported product lanes:

- Unreal/Mixamo/FBX source animation to KOTOR target model.
- KOTOR source animation to KOTOR target model.
- KOTOR source animation to Unreal target skeleton.

Exports should only happen after preview and readback gates pass. Vanilla-slot
overrides and custom animation patches are separate output modes.

### Character Studio

Character Studio is the custom-character pipeline. The intended modder flow is:

1. Choose a base KOTOR model/skeleton.
2. Load a custom mesh.
3. Auto-fit using native KOTOR landmarks and reference bounds.
4. Fine-tune guides and mesh fit.
5. Clone/confirm the native KOTOR node hierarchy.
6. Bind skin rows.
7. Assign inherited supermodel or local animations.
8. Preview heads, weapons, masks, goggles, belts, and attachments.
9. Run validation/export preflight.
10. Export MDL/MDX candidates and test in game.

Do not claim a custom character is game-ready until viewport preview, export
readback, and in-game testing have passed.

### Module Studio And Map Studio

Module Studio edits existing KOTOR module resources. Map Studio authors custom
modules and areas. Both must preserve source game data unless the user
explicitly chooses an export/write operation.

Current first Map Studio proof target:

```text
grdev01
```

`grdev01` is a generated KOTOR 1 dev-test module with authored room
MDL/MDX/WOK, ARE/GIT/IFO/PTH/LYT/VIS, a player start, one test placeable,
staged `.mod`, and required `warp grdev01` screenshot/video proof before it can
be called game-tested.

## FBX Backends

GhostRigger keeps FBX backends explicit.

| Backend | Use | Notes |
|---------|-----|-------|
| Blender Headless | Production FBX import/export bridge for animation and mesh extraction. | Requires Blender 4.2 LTS or `GHOSTRIGGER_BLENDER_PATH`. |
| Autodesk FBX SDK | Optional SDK-backed path. | Must be installed manually. SDK binaries are not committed or bundled. |
| Generic Assimp paths | Legacy/static mesh import support. | Useful for some main-viewport file imports, not a replacement for Retarget Studio animation import. |

Autodesk SDK smoke check:

```bat
python -c "import fbx; m=fbx.FbxManager.Create(); print(m.GetVersion()); m.Destroy()"
```

Blender is not treated as a silent fallback for Autodesk SDK requests. If a
workflow asks for Autodesk and the SDK is missing, GhostRigger should fail with
an actionable setup message unless that workflow explicitly opts into a
fallback.

## Validation And Export Safety

Export workflows should:

1. Run validation/preflight before writing.
2. Stage output files.
3. Verify staged outputs.
4. Promote files only after verification.
5. Avoid partial writes.
6. Report actionable issues through `ValidationBus`.

KOTOR source data should never be overwritten silently.

## Testing

Prefer targeted checks:

```bat
python -m py_compile main.py
python -m pytest tests/test_fbx_backend_registry.py -q
python -m pytest tests/test_character_builder_template_rig.py -q
python -m pytest tests/test_headless_body_workflow.py -q -k "external_model_normalization or generated_rom"
```

Use MCP/game-file validation tools for model-pipeline truth: MDL loading,
vertex transforms, textures, skinning, model comparison, and game-file parsing.

Visible UI, startup, viewport, theme/layout, renderer, animation playback, and
workflow behavior must be tested in the real GhostRigger Debug application.
Backend probes are not a substitute for visible workflow testing.

Do not run broad full scans unless the task explicitly requires them.

## Repository Map

```text
src/                         Canonical Python source for app and domain logic.
native/                      Visual Studio C++ package tree and embedded Python payloads.
config/                      Themes, layouts, and runtime configuration assets.
assets/icons/                Application icon assets.
examples/                    Example KMAX/KMAP and workflow data.
scripts/                     Build, payload, validation, smoke, and utility scripts.
tests/                       Targeted unit, contract, workflow, native, and regression tests.
knowledge_base/              Active roadmap, architecture, native migration, and references.
docs/knowledgebase/          Local book-derived agent skill notes.
```

## Documentation

Start here:

- [Active roadmap](knowledge_base/roadmap/02_roadmap_2026_05.md)
- [Roadmap index](knowledge_base/roadmap/README.md)
- [Package ownership model](knowledge_base/package_ownership_model.md)
- [Native migration plan](knowledge_base/native_migration_plan.md)
- [C++ integration phases](knowledge_base/cpp_integration_phases.md)
- [Knowledge base index](knowledge_base/README.md)
- [Agent operating manual](AGENTS.md)

## Branch And Contribution Policy

- Primary development branch: `qt-ghostrigger`.
- Legacy branches are historical references; do not base new feature work on
  them.
- Commit messages should include the relevant roadmap task ID when one applies.
- Future PRs should target `qt-ghostrigger`.
- Keep generated output, proprietary game assets, local screenshots, books, and
  dependency caches out of commits unless a tracked fixture is explicitly
  required.

## License And Legal

See [LICENSE](LICENSE).

GhostRigger does not bundle KOTOR game assets or Autodesk FBX SDK binaries.
Users are responsible for using legal local game installs and third-party SDKs
according to their licenses.
