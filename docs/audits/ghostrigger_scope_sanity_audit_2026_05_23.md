# GhostRigger Scope Sanity Audit

Date: 2026-05-23
Branch: `qt-ghostrigger`

## 1. What GhostRigger Is For

GhostRigger's plan is to become a KOTOR/Odyssey modding suite with four product
studios:

1. Character Studio: import or build characters, bind them to native KOTOR
   Aurora hierarchies, preview animation, and export safe MDL/MDX candidates.
2. Retarget Studio: retarget animation between Unreal/FBX and KOTOR, and
   between KOTOR models, with preview-first and export-last discipline.
3. Module Studio: inspect, edit, validate, and save module resources safely.
4. Map/Scenario Studio: build layouts, place objects, author scenario data, and
   package installable module outputs.

The real goal is not "make a 3D editor". The goal is:

```text
Give KOTOR modders a safe, visual, game-aware workflow from idea to tested
KOTOR artifact.
```

## 2. Scope Boundaries

In scope:

- KOTOR/Odyssey resource browsing, inspection, validation, and export staging.
- KOTOR-native MDL/MDX preview and write/readback validation.
- Retargeting that produces KOTOR-compatible animation blocks or UE-compatible
  export candidates.
- Character workflows that preserve native Aurora node DAGs, hooks, supermodel
  semantics, skin metadata, texture names, and MDX layout.
- Module/Map workflows that respect resrefs, restypes, templates, placed GIT
  instances, LYT/VIS/WOK, and patch/install safety.

Out of scope unless serving one of the four studios:

- generic DCC modeling;
- generic game-engine editing;
- broad Unreal tooling unrelated to KOTOR import/export;
- patch installation that bypasses staged manifests;
- Ghidra as a user-facing product feature;
- one-off MDL fix scripts without tests or named product modes.

## 3. Current Program State

### Working foundations

- `GhostRiggerProject` and `ResourceAddress` exist.
- `ValidationBus` exists.
- `ExportJob` exists and retarget export uses it.
- Retarget Workbench supports `Unreal to KOTOR` and `KOTOR to KOTOR`.
- Retarget output names support vanilla slots and custom animation patch names.
- Retarget Workbench readiness/status explains mode, source, target, output,
  runtime safety, preview readiness, and export readiness.
- The MDL animation injection path has hard-won PMBAM lessons: preserve case,
  hierarchy, controllers, and vanilla mesh/skin payloads where possible.

### Partial but promising

- Character Studio has substantial import/HUD/workflow pieces, but native KOTOR
  DAG export remains the launch-critical gap.
- Module Studio has strong backend hydration, object inspection, save, reference
  safety, and WOK services, but product safety needs provider-backed state,
  undo, and ExportJob migration.
- Map Studio has KMAP/KMAX, LYT/VIS/WOK, snap, and package services, but scenario
  authoring and UI cohesion remain incomplete.
- Sequence/Cutscene tooling exists, but it is not yet bound cleanly to module,
  map, script, and resource-provider workflows.

### Pending

- `KOTOR to Unreal` retarget/export.
- Shared `GameResourceProvider`.
- Provider-backed Qt resource models.
- Shared ValidationBus issue panel.
- Shared undo command foundation.
- Shared job/progress/cancel service bridge.
- Character Studio native KOTOR DAG lock.
- Module/Map export migration through ExportJob.
- Patch Manager staging/install workflow.

## 4. Honest Product Assessment

GhostRigger currently works extremely well as an advanced technical workbench,
especially for KOTOR model inspection, viewport validation, and retargeting.
The recent retargeting work is genuinely strong: it has source sampling,
preview, output naming, export staging, readback verification, and KOTOR-specific
runtime honesty.

It is not yet a polished all-in-one modder suite. The program has many real
subsystems, but the modder-facing workflow still needs a shared resource spine,
consistent state labels, undoable authoring, and a unified issue/export surface.

The highest risk is not lack of capability. It is capability fragmentation.

## 5. Scope Risks

| Risk | Why it matters | Correction |
|---|---|---|
| Feature spread across four studios | Powerful systems can become hard to understand | Enforce studio ownership and use-case names. |
| `qt_main_window.py` grows as the command brain | UI becomes business logic | Move commands to controllers/services and QAction registry. |
| Resource lookup stays duplicated | Different studios may see different truth | Build `GameResourceProvider` before richer browsers/editors. |
| Module/Map edits without undo | Modders can corrupt authoring state | Add undo command foundation before broad save workflows. |
| Writer/export paths outside ExportJob | Partial files and unsafe overwrites return | Migrate all writes to ExportJob. |
| Community docs used as binary truth | MDL/MDX regressions and game crashes | Use Tier 1 implementation/MCP/Ghidra truth for binary behavior. |
| Overclaiming readiness | Users may trust untested outputs | Use implemented/previewable/export-candidate/game-tested labels. |

## 6. What To Do Next

The next architecture slice after the new provider foundation should be:

```text
T2305: provider-backed resource browser models
```

T2304 now supplies the read-only provider contracts and adapters. T2305 should
put those provider results behind Qt model/view resource lists so modders see
consistent resref/restype/layer/provenance rows across studios.

The next UI infrastructure slice should be:

```text
T2306: ValidationBus issue model/panel
```

The next safety/productization slices should be:

```text
T2306: ValidationBus issue model/panel
T2307: undo command foundation
T2308: shared job/progress bridge
```

The next product slices should be:

```text
Retarget: named quality/correction modes and game-tested labels
Character: NativeSkeletonSnapshot and clone-native-DAG bind/export path
Module/Map: provider-backed read-only resource browsing, then undoable edits
```

## 7. Scope Sanity Rule

Every feature prompt should now begin with:

```text
This belongs to Studio X.
It lets a KOTOR modder do Y.
It reads/edits/exports resource Z.
It is query-only / previewable / export-candidate / game-tested.
It uses ValidationBus and ExportJob when appropriate.
It leaves these things incomplete.
```

If that cannot be written clearly, the feature is not ready.
