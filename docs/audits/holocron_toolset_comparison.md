# Holocron Toolset / PyKotor Comparison

Date: 2026-05-23

## 1. Source Map and Checkout Notes

The requested checkout target was:

`C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/HolocronToolset-PyKotor`

Attempted clone of the current OpenKotOR/PyKotor repository failed because the
local Git TLS certificate chain was not trusted. TLS was not weakened. The audit
therefore used the existing local research checkout:

`C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/PyKotor`

Current upstream source checked by web:

`https://github.com/OpenKotOR/PyKotor`

The local checkout may still point at an older remote; do not assume its remote
name is authoritative without checking.

Local repo notes:

- root project: `pykotor-workspace`;
- package version observed in `pyproject.toml`: `2.3.12`;
- license: `LGPL-3.0-or-later`;
- submodules for `Tools/HolocronToolset`, `Tools/HoloPatcher`, and others are
  declared but not initialized locally;
- `Tools/README.md` points at the OpenKotOR/PyKotor repository family;
- local working tree has unrelated dirty changes in PyKotor and was not edited.

Web/source references consulted:

- PyKotor / Holocron wiki: https://github-wiki-see.page/m/OpenKotOR/PyKotor/wiki
- PyKotor package metadata: https://pypi.org/project/pykotor/
- Holocron Toolset DeadlyStream page: https://deadlystream.com/files/file/1982-holocron-toolset/
- KotorBlender: https://github.com/seedhartha/KotorBlender
- MDLOps: https://github.com/ndixUR/mdlops
- xoreos: https://xoreos.org/
- NWN Aurora conceptual MDL docs: https://nwn.wiki/display/NWN1/MDL
- NWN animation conceptual docs: https://nwn.wiki/display/NWN1/Animations

## 2. PyKotor / Holocron Feature Inventory

The local PyKotor checkout contains a mature headless resource library:

| Capability | PyKotor/Holocron area | Notes |
|---|---|---|
| KEY/BIF/RIM/ERF/MOD loading | `Libraries/PyKotor/src/pykotor/extract`, `resource/formats/*` | Strong archive/resource foundation. |
| Module abstraction | `pykotor/common/module.py` | Handles `.rim`, `_a.rim`, `_adx.rim`, `_s.rim`, `_dlg.erf`, `.mod` module pieces and resource ownership rules. |
| GFF and generics | `resource/formats/gff`, `resource/generics/*` | Typed models for ARE, DLG, GIT, IFO, JRL, PTH, UTC, UTD, UTE, UTI, UTM, UTP, UTS, UTT, UTW. |
| 2DA/TLK | `resource/formats/twoda`, `resource/formats/tlk` | Mature parsers/writers for core tables/dialog text. |
| Walkmesh/BWM | `resource/formats/bwm`, `common/indoormap.py` | Used in indoor map/module builder paths. |
| MDL | `resource/formats/mdl` | Useful reference, but GhostRigger still needs its own game-tested writer behavior for animation export. |
| NSS/NCS | `resource/formats/ncs`, compiler/decompiler packages | Good candidate behind a GhostRigger `ScriptService`. |
| Indoor map builder | `pykotor/common/indoormap.py` | Headless map/module builder producing ERF `.mod`, LYT, VIS, ARE, IFO, GIT, BWM/TPC data. |
| Patching/install | HoloPatcher / TSLPatcher packages in monorepo metadata | Useful for install staging and compatibility strategy. |
| GUI toolset | Holocron Toolset package/submodule | Not locally initialized, but wiki and package metadata confirm broad editor coverage. |

## 3. Useful Design Ideas for GhostRigger

1. Keep resource formats headless and UI-free. PyKotor places data models and
   builders under library modules, with GUI tools elsewhere.
2. Treat module pieces explicitly. The `KModuleType` model is a good conceptual
   reference for GhostRigger's `GameResourceProvider`.
3. Use typed GFF generics for Module Studio forms instead of ad hoc field logic.
4. Keep indoor/map building as a staged data model that produces module
   resources, not as direct live archive mutation.
5. Use patcher/install outputs as final staging products, not as normal preview
   or authoring state.

## 4. Useful Reusable Libraries

GhostRigger should prefer the following integration styles:

- dependency/library use for PyKotor parsers, typed generics, and module helpers;
- subprocess or tool boundary for patcher/installer workflows if distribution
  or LGPL concerns make direct linking undesirable;
- conceptual reference only for Holocron GUI patterns unless the submodule is
  initialized and license/reuse is reviewed.

Do not copy PyKotor/Holocron code into GhostRigger without a license decision.
PyKotor is LGPL-3.0-or-later while GhostRigger is MIT.

## 5. Comparison Table

| Area | Holocron/PyKotor capability | GhostRigger capability | Gap | Recommendation |
|---|---|---|---|---|
| Resource/archive access | Mature KEY/BIF/RIM/ERF/MOD and installation APIs | Game loader, PyKotor bridge, MCP resource tools | GhostRigger resource access is spread across subsystems | Add `GameResourceProvider` and use PyKotor for archive/GFF truth where practical. |
| GFF object editing | Typed generics for ARE/GIT/UTC/UTP/etc. | Module object inspector and local GFF reader/writer | GhostRigger forms are less complete | Back Module Studio forms with PyKotor generics. |
| Module editor | Holocron Module Designer/Indoor Builder concepts | KMAP/KMAX, module hydration/save, module editor UI | GhostRigger has stronger 3D ambitions but less mature typed editor coverage | Combine GhostRigger 3D viewport with PyKotor-style typed resource models. |
| Map/indoor builder | `IndoorMap` headless builder and kit concepts | KMAP/KMAX, LYT/VIS/WOK services, custom packager | GhostRigger needs product integration | Borrow kit/module-builder concepts; keep KMAP as GhostRigger authoring format. |
| Patching/install | HoloPatcher/TSLPatcher-style ecosystem | Custom module packager, Patch Manager workflows outside this repo, and shared `ExportJob` foundation | Need migration and staging conventions for non-retarget outputs | Use `ExportJob` for package staging and optional HoloPatcher/Patch Manager manifests. |
| MDL animation retargeting | Not the main Holocron strength | Strong Retarget Studio gates and GhostRigger viewport | GhostRigger should keep owning this | Use PyKotor/MDLOps/KotorBlender only as validation references. |
| Character import/rigging | Limited compared to GhostRigger goals | Character Builder/autorig/retarget stack | GhostRigger has unique scope but export not fully proven | Continue native KOTOR DAG Character Studio plan. |
| 3D visual scenario authoring | Module Designer exists, but advanced cutscene/battle authoring is limited | KMAP/KMAX/sequence foundation | Neither is complete | GhostRigger can differentiate here. |
| Script/dialog authoring | PyKotor has formats/compiler pieces; Holocron editors exist | GhostRigger has IPC hooks and MCP/decompile tools | No unified ScriptService | Bridge PyKotor/GhostScripter as services. |

## 6. Gaps Holocron Does Not Cover for GhostRigger Goals

Holocron/PyKotor should not be expected to solve:

- custom character import, rigging, and KOTOR-native MDL/MDX skin export;
- UE/FBX to KOTOR or KOTOR to UE animation retargeting;
- exact GhostRigger viewport quality gates;
- advanced cutscene/battle sequence authoring tied to 3D scene state;
- GhostRigger-specific KMAX/KMAP scene and map workflows;
- in-game retargeted animation validation for custom MDL animation overrides.

## 7. Recommendations for GhostRigger

1. Use PyKotor for resource format truth, module archive rules, typed GFF models,
   and script/NCS infrastructure.
2. Keep GhostRigger's value-add in 3D visual authoring, MDL/MDX preview/export,
   retargeting, character rigging, and scenario workflows.
3. Do not duplicate Holocron's standalone resource editors unless GhostRigger is
   adding 3D context, validation, or cross-studio integration.
4. Keep Holocron/PyKotor as a local research/dependency checkout, not vendored
   code.
5. Initialize Holocron Toolset submodules later if network/TLS allows, then run
   a narrower UI/editor comparison.
