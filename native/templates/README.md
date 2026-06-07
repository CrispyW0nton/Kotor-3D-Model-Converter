# GhostRigger Native Project Templates

These templates are Phase 1 scaffolding for new C++ packages in
`GhostRigger.sln`. They are intentionally small and explicit so future agents
create native projects with the same output layout, warning level, language
standard, ownership metadata, and DEBUG executable expectations.

Use these templates when adding:

- a shared native package used by multiple renderer/toolbox systems;
- a renderer DLL package;
- a toolbox DLL package;
- a package DEBUG executable.

The anchor native projects are `GhostRigger.Native`, `GhostRigger.Native.NativeCore`,
and `GhostRigger.Runtime`. Shared follow-on packages should use
`GhostRigger.Native.NativeCore.{System}` for core foundations and `GhostRigger.Runtime.Shared.{System}` for
runtime contracts consumed by multiple renderer/toolbox packages.

Toolbox and window migrations must use product-surface namespaces rather than
being folded into the host or runtime projects. Native toolbox packages use
`GhostRigger.Tools.{Toolname}`, for example `GhostRigger.Tools.Retargeting` or
`GhostRigger.Tools.Export`. The Phase 1 native main-window package is
`GhostRigger.Windows.MainWindow`. Shared logic that more than one tool or
window consumes still belongs in `GhostRigger.Native.NativeCore.*` or
`GhostRigger.Runtime.Shared.*` first.

Do not copy an existing feature project and then strip it down. Start from the
matching template and replace every `{{TOKEN}}`.

## Required Tokens

| Token | Meaning |
|-------|---------|
| `{{PROJECT_NAME}}` | Visual Studio project and target name, such as `GhostRigger.Tools.Retargeting`, `GhostRigger.Windows.MainWindow`, or `GhostRigger.Renderer.D3D12`. |
| `{{PROJECT_GUID}}` | New project GUID in braces. |
| `{{ROOT_NAMESPACE}}` | C++ root namespace or project namespace. |
| `{{EXPORT_DEFINE}}` | DLL export preprocessor define, such as `GHOSTRIGGER_RENDERER_D3D12_EXPORTS`. |
| `{{OWNER_SURFACE}}` | Product surface owner, such as Main Viewport/KMAX or Character Studio. |
| `{{OWNER_PACKAGE}}` | Owning code package path. |
| `{{BRIDGE_METHOD}}` | C ABI, `.pyd`, host module, or shared-handle API. |

## Mandatory New Project Checklist

1. Add the project directory under `native/{{PROJECT_NAME}}/`.
2. Add a DEBUG executable under `native/{{PROJECT_NAME}}DEBUG/` unless the
   project is DEBUG-only.
3. Add both projects to `GhostRigger.sln` with Debug/Release and Win32/x64
   mappings. DEBUG executable projects must not have `Release|Win32.Build.0`
   or `Release|x64.Build.0` entries in the solution.
4. Add `GhostRigger.Native.NativeCore` as a dependency when the package uses shared
   handles, diagnostics, or capability contracts.
5. Add Python detection through `src.adapters.native_core.package_registry`
   when Python must query the package without starting the GUI.
6. Update `knowledge_base/cpp_integration_phases.md`, `native/README.md`, and
   `CHANGES.md`.
7. Include `Owner: LordVaderCW` and `Intersects:` in the changelog entry.
8. Run Debug x64 plus the package DEBUG executable, then run Release x64 and
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
- Native DEBUG:
- Python adapter test:
- Visible app check:
```

This mirrors the project-boundary rules in
`knowledge_base/cpp_integration_phases.md`.
