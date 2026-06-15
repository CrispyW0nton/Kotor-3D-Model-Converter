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

Toolbox and window migrations must use product-surface namespaces rather than
being folded into the host or runtime projects. Native toolbox packages use
`GhostRigger.Tools.Workflow.{Toolname}`, for example `GhostRigger.Tools.Workflow.Retargeting` or
`GhostRigger.Tools.Workflow.Export`. The Phase 1 native main-window package is
`GhostRigger.Windows.Shell.Main`. Shared logic that more than one tool or
window consumes still belongs in `GhostRigger.Native.Core.Foundation.*` or
`GhostRigger.Runtime.Shared.*` first.

Renderer contract packages use `GhostRigger.Renderer.Shared.Contracts`. Concrete
renderer backend packages use `GhostRigger.Renderer.Backend.{Backend}`, for example
`GhostRigger.Renderer.Backend.D3D12` or the diagnostic `GhostRigger.Renderer.Backend.Null`.

Do not copy an existing feature project and then strip it down. Start from the
matching template and replace every `{{TOKEN}}`.

## Required Tokens

| Token | Meaning |
|-------|---------|
| `{{PROJECT_NAME}}` | Visual Studio project and target name, such as `GhostRigger.Tools.Workflow.Retargeting`, `GhostRigger.Windows.Shell.Main`, or `GhostRigger.Renderer.Backend.D3D12`. |
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
4. Add the package project to `GhostRigger.sln` with Debug/Release and Win32/x64
   mappings. `.DEBUG` application projects must not be added to the solution.
5. Add `GhostRigger.Native.Core.Foundation` as a dependency when the package uses shared
   handles, diagnostics, or capability contracts.
6. Add Python detection through `src.adapters.native_core.package_registry`
   when Python must query the package without starting the GUI.
7. Update `knowledge_base/cpp_integration_phases.md`, `native/README.md`, and
   `CHANGES.md`.
8. Include `Owner: LordVaderCW` and `Intersects:` in the changelog entry.
9. Run the real project in Debug x64, then run Release x64 and
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
