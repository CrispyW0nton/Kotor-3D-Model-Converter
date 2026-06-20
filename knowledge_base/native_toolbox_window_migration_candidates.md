# GhostRigger Native Toolbox And Window Migration Candidates

Date: 2026-06-07
Branch: `qt-ghostrigger`
Related: `knowledge_base/package_ownership_model.md`, `knowledge_base/cpp_integration_phases.md`, `knowledge_base/native_migration_plan.md`, `native/README.md`

## Purpose

This document records the first concrete Phase 1 candidates for Python-to-C++
toolbox, GUI Display, GUI Helpers, and host-service migration. It is a planning
foundation only: it does not move UI behavior or replace Python workflows. Each
candidate names the native project, owner surface, bridge method, ownership
boundary, and verification gate that must exist before implementation begins.

Shared logic used by more than one candidate must be moved into
the canonical owner in `knowledge_base/package_ownership_model.md` before a
toolbox, GUI, renderer, runtime, or adapter package consumes it.

## Naming Rules

- Toolbox packages use `GhostRigger.Core.Tools.{Toolname}`.
- Visible UI packages use `GhostRigger.Core.GUI.Display.*`.
- Interactive helper packages use `GhostRigger.Core.GUI.Helpers.*`.
- Host-service/native lifecycle surfaces use `GhostRigger.Native.Core.*`,
  `GhostRigger.Runtime.*`, `GhostRigger.Core.Automation`, or
  `GhostRigger.Core.Bridge.NativeHost` according to ownership.
- Existing `GhostRigger.Core.GUI.Display.*` packages are legacy Phase 1 compatibility
  projects. Do not add a new generic `GhostRigger.Core.GUI.Display.<Type>.<WindowName>`
  project.

## Candidate: Retargeting Tool

Native project: `GhostRigger.Core.Tools`
Owner surface: Retarget Workbench
Owner package: `native/GhostRigger.Core.Tools`
Bridge method: C ABI DLL first; `.pyd` only if the retargeting API needs richer
Python types after the C ABI contract proves too narrow.

Data ownership:

- C++ owns: hot pose-palette blending helpers, numeric retarget solve packets,
  solver diagnostics, and future batch validation helpers.
- Python owns: KOTOR animation source selection, UI state, user workflow,
  export policy, project/session persistence, and MCP-backed truth checks.

Verification gates:

- Native Debug target: build `GhostRigger.Core.Tools` in `Debug|x64`.
- Python adapter test: targeted adapter/package availability and solve-packet
  fallback checks.
- Backend truth check: MCP animation fixture comparison when native retargeting
  begins changing model or animation outputs.
- Visible app check: required only when a future slice changes Retarget
  Workbench UI/workflow behavior.

## Candidate: Export Tool

Native project: `GhostRigger.Core.Tools`
Owner surface: Export and validation workflow
Owner package: `native/GhostRigger.Core.Tools`
Bridge method: C ABI DLL for validator/readback helpers before any writer
replacement.

Data ownership:

- C++ owns: optional native readback/validation helpers, packed buffer
  diagnostics, and performance-sensitive export preflight checks.
- Python owns: export decisions, file-format policy, game-resource semantics,
  write prompts, dirty-scene safety, and final writer orchestration until native
  parity is proven.

Verification gates:

- Native Debug target: build `GhostRigger.Core.Tools` in `Debug|x64`.
- Python adapter test: targeted export-helper fallback checks.
- Backend truth check: PyKotor/GhostRigger reload comparison before any native
  helper becomes authoritative.
- Visible app check: required only when a future slice changes export dialogs or
  user workflow.

## Candidate: Character Builder Tool

Native project: `GhostRigger.Core.Tools`
Owner surface: Character Studio
Owner package: `native/GhostRigger.Core.Tools`
Bridge method: C ABI DLL for numeric autofit, skinning, and validation helpers.

Data ownership:

- C++ owns: hot autofit math helpers, native skinning validation packets, and
  diagnostic readback helpers.
- Python owns: Character Studio UI, source asset selection, game semantics,
  save/export decisions, and MCP-backed validation.

Verification gates:

- Native Debug target: build `GhostRigger.Core.Tools` in `Debug|x64`.
- Python adapter test: targeted helper availability and missing-DLL fallback.
- Backend truth check: representative character fixtures before native helper
  output replaces Python behavior.
- Visible app check: required only when a future slice changes Character Studio
  UI/workflow behavior.

## Candidate: Main Window Host Surface

Current legacy native project: `GhostRigger.Core.GUI.Display`
Canonical target owner: `GhostRigger.Core.GUI.Display` for visible shell
composition, `GhostRigger.Core.GUI.Display` for dock/panel display,
`GhostRigger.Core.Automation.Commands` for command routing, or
`GhostRigger.Core.Bridge.NativeHost` for native host-service glue.
Owner surface: Main window composition shell
Owner package: `native/GhostRigger.Core.GUI.Display`
Bridge method: host module or C ABI bridge only after the Python/Qt main window
has a narrow native service to call.

Data ownership:

- C++ owns: future host-owned native services that are genuinely shared by the
  application shell, such as native command routing or host service discovery.
- Python owns: current Qt widgets, docks, menus, themes, layouts, window state,
  user workflow orchestration, and visible shell behavior.

Verification gates:

- Native Debug target: build `GhostRigger.Core.GUI.Display` in `Debug|x64`.
- Python adapter test: targeted host-service discovery and fallback checks.
- Backend truth check: not applicable unless the slice touches model/data
  pipelines.
- Visible app check: required for any future slice that changes startup,
  theming, layout, docking, menus, or visible main-window workflow.
