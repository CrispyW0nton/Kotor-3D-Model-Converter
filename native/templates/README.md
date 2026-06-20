# GhostRigger Native Project Templates

These templates are Phase 1 scaffolding for new C++ packages in
`GhostRigger.sln`. They are intentionally small and explicit so future agents
create native projects with the same output layout, warning level, language
standard, ownership metadata, and Debug-configuration verification expectations.

Use these templates when adding:

- a shared native package used by multiple renderer/toolbox systems;
- a renderer DLL package;
- a toolbox DLL package;
- a package Debug-configuration verification contract.

The anchor native projects are `GhostRigger.Native.Core.Host`, `GhostRigger.Native.Core.Foundation`,
and `GhostRigger.Runtime.Core.Host`. Shared follow-on packages should use
`GhostRigger.Native.Core.Foundation.{System}` for core foundations and `GhostRigger.Runtime.Shared.{System}` for
runtime contracts consumed by multiple renderer/toolbox packages.

Toolbox migrations must use product-surface namespaces rather than being folded
into the host or runtime projects. Native toolbox packages use
`GhostRigger.Core.Tools.{Toolname}`, for example
`GhostRigger.Core.Tools.Retargeting`, `GhostRigger.Core.Tools.Export`, or
`GhostRigger.Core.Tools.ModuleEditor`. Visible windows, panels, dialogs,
widgets, controls, notifications, overlays, and display-only state belong under
`GhostRigger.Core.GUI.Display.*`. Interactive helper objects such as gizmos,
selection pickers, transform handles, snapping helpers, and dummies belong
under `GhostRigger.Core.GUI.Helpers.*`. Broad `GhostRigger.Core.GUI.Display.*` projects
are legacy compatibility boundaries and are not naming precedent for new
projects.

Renderer packages use `GhostRigger.Core.Rendering.*`. Renderer-neutral
contracts belong in `GhostRigger.Core.Rendering`, and concrete backend packages
use `GhostRigger.Core.Rendering.Backends.{Backend}`, for example
`GhostRigger.Core.Rendering.Backends.D3D12` or the diagnostic
`GhostRigger.Core.Rendering.Backends.Null`. Existing
`GhostRigger.Core.Rendering.Contracts` and
`GhostRigger.Core.Rendering.Backends.*` projects are the current canonical
renderer contract/backend package names.

Shared logic that more than one tool, GUI package, renderer, or runtime package
consumes belongs in the canonical Core, Systems, Runtime, Native Core, or
Adapters owner first. Follow `knowledge_base/package_ownership_model.md` before
choosing a new package name.

Do not copy an existing feature project and then strip it down. Start from the
matching template and replace every `{{TOKEN}}`.

## Required Tokens

| Token | Meaning |
|-------|---------|
| `{{PROJECT_NAME}}` | Visual Studio project and target name, such as `GhostRigger.Core.Tools.Retargeting`, `GhostRigger.Core.GUI.Display.Panels`, or `GhostRigger.Core.Rendering.Backends.D3D12`. |
| `{{PROJECT_GUID}}` | New project GUID in braces. |
| `{{ROOT_NAMESPACE}}` | C++ root namespace or project namespace. |
| `{{EXPORT_DEFINE}}` | DLL export preprocessor define, such as `GHOSTRIGGER_RENDERER_D3D12_EXPORTS`. |
| `{{OWNER_SURFACE}}` | Product surface owner, such as Main Viewport/KMAX or Character Studio. |
| `{{OWNER_PACKAGE}}` | Owning code package path. |
| `{{BRIDGE_METHOD}}` | C ABI, `.pyd`, host module, or shared-handle API. |

## Mandatory New Project Checklist

1. Add the project directory under `native/{{PROJECT_NAME}}/`.
2. Do not add a parallel `.DEBUG` application project. Debug validation runs
   through the real project's `Debug|x64` configuration in `GhostRigger.sln`.
3. Put public headers in `Public/`, private implementation files in `Private/`,
   and embedded Python copies in `Python/`.
4. Confirm the package name matches `knowledge_base/package_ownership_model.md`
   and is not a duplicate owner that should be merged instead.
5. Add the package project to `GhostRigger.sln` with Debug/Release and Win32/x64
   mappings. `.DEBUG` application projects must not be added to the solution.
6. Add `GhostRigger.Native.Core.Foundation` as a dependency when the package uses shared
   handles, diagnostics, or capability contracts.
7. Add Python detection through `src.adapters.native_core.package_registry`
   when Python must query the package without starting the GUI.
8. Update `knowledge_base/package_ownership_model.md` only if a new owner class
   is intentionally created; otherwise update package-specific docs to point at
   the existing canonical owner.
9. Update `knowledge_base/cpp_integration_phases.md`, `native/README.md`, and
   `CHANGES.md`.
10. Include `Owner: LordVaderCW` and `Intersects:` in the changelog entry.
11. Run the real project in Debug x64, then run Release x64 and
   confirm the Release output contains only `.exe`, `.dll`, and `.lib` files.

## Ownership Header

Every new native package README should include:

```text
Owner surface: {{OWNER_SURFACE}}
Owner package: {{OWNER_PACKAGE}}
Bridge method: {{BRIDGE_METHOD}}
Data ownership:
- C++ owns:
- Python owns:
Verification:
- Native Debug target:
- Python adapter test:
- Visible app check:
```

This mirrors the project-boundary rules in
`knowledge_base/cpp_integration_phases.md`.
