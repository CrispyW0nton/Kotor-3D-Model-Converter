# GhostRigger Package Ownership Model

Date: 2026-06-20
Owner: LordVaderCW
Status: Architecture authority

This document is the canonical package ownership model for GhostRigger. When
older repository documents, package names, planning notes, manifests, READMEs,
or tests disagree with this model, update them toward this model. Existing
Visual Studio projects that still use legacy names are compatibility state, not
new naming precedent.

## Prime Rule

Every package must have a durable reason to exist. Keep a separate project only
when it represents a real runtime, ABI, adapter, product, subsystem, dependency,
or deployment boundary. Merge projects when they are thin wrappers, duplicate
another owner, split one feature without a real ownership reason, or preserve a
past naming batch rather than a current architectural boundary.

Do not rename a live native project only in one manifest. A project rename must
update the directory, `.vcxproj`, filters, solution, payload manifests, resource
scripts, package registry entries, tests, and compatibility shims together.

## Canonical Owners

### IO

All file behavior belongs under IO: reading, writing, importing, exporting,
serialization, deserialization, MDL extraction, MDL packing, FBX import/export,
archive access, resource-file access, and format conversion.

Canonical names include:

- `GhostRigger.Core.IO.File.Format`
- `GhostRigger.Core.IO.File.Format`
- `GhostRigger.Core.IO.Import`
- `GhostRigger.Core.IO.Export`
- `GhostRigger.Core.IO.Resources`
- `GhostRigger.Core.IO.Serialization`

### Automation

Automation behavior belongs under Core Automation: IPC, MCP, scripting bridges,
external control APIs, background automation, command automation, automation
events, and machine-facing integration.

Canonical names include:

- `GhostRigger.Core.Automation`
- `GhostRigger.Core.Automation`
- `GhostRigger.Core.Automation.Commands`
- `GhostRigger.Core.Automation`

### Tools

User-facing tools and product workflows belong under Core Tools. Tools may
orchestrate IO, GUI, Automation, Resources, Math, Scene, Rendering, Validation,
or lower-level workflow systems, but they must not own lower-level reusable
behavior.

Canonical names include:

- `GhostRigger.Core.Tools.CharacterBuilder`
- `GhostRigger.Core.Tools.Retargeting`
- `GhostRigger.Core.Tools.ModuleEditor`
- `GhostRigger.Core.Tools.ResourceBrowser`
- `GhostRigger.Core.Tools.Export`
- `GhostRigger.Core.Tools.PivotControls`

### GUI Display

Anything displayed on screen belongs under GUI Display: buttons, logos, icons,
status notifications, widgets, panels, toolbars, overlays, labels, menus,
dialogs, visible controls, and display-only view state.

Canonical names include:

- `GhostRigger.Core.GUI.Display.Buttons`
- `GhostRigger.Core.GUI.Display.Icons`
- `GhostRigger.Core.GUI.Display.Notifications`
- `GhostRigger.Core.GUI.Display.Panels`
- `GhostRigger.Core.GUI.Display.Widgets`
- `GhostRigger.Core.GUI.Display.Overlays`

GUI Display owns presentation, layout, styling, signals, and visible UI state.
It must not own file IO, parsing, packing, export logic, durable scene policy,
or core algorithms.

### GUI Helpers

Interactive helper objects belong under GUI Helpers: gizmos, dummies,
manipulators, transform handles, viewport pickers, selection helpers, guides,
snapping helpers, drag handles, and similar user-interaction helpers.

Canonical names include:

- `GhostRigger.Core.GUI.Helpers.Gizmo`
- `GhostRigger.Core.GUI.Helpers.SelectionPicker`
- `GhostRigger.Core.GUI.Helpers.TransformHandle`
- `GhostRigger.Core.GUI.Helpers.Dummy`
- `GhostRigger.Core.GUI.Helpers.Snapping`

Helpers may visualize or manipulate core state. Durable rules and algorithms
belong in the correct Core, Math, IO, Scene, Rendering, Validation, or Tool
package.

### Scene

Scene state, scene objects, transforms, pivots, object hierarchy, selection
state, placement, and scene serialization contracts belong under Scene.

Canonical names include:

- `GhostRigger.Core.Scene`
- `GhostRigger.Core.Scene.Objects`
- `GhostRigger.Core.Scene.Transforms`
- `GhostRigger.Core.Scene.Selection`
- `GhostRigger.Core.Scene.KMAX`

### Resources

Resource discovery, resource identity, resource addresses, references,
lifetime, cache policy, and game/library lookup belong under Resources.

Canonical names include:

- `GhostRigger.Core.Resources`
- `GhostRigger.Core.Resources.Discovery`
- `GhostRigger.Core.Resources.Addressing`
- `GhostRigger.Core.Resources.Cache`
- `GhostRigger.Core.Resources.GameLibrary`

### Formats

Pure format structures and format-level contracts belong under Formats unless
the behavior is specifically read/write IO. Formats define structure; IO reads
and writes it.

Canonical names include:

- `GhostRigger.Core.IO.File.Format.MDL`
- `GhostRigger.Core.IO.File.Format.TPC`
- `GhostRigger.Core.IO.File.Format`
- `GhostRigger.Core.IO.File.Format.KMAX`
- `GhostRigger.Core.IO.File.Format.KMAP`

### Math

Reusable math belongs under Math: transforms, matrices, cameras, pivots,
projections, coordinate conversion, normals, tangents, skinning math, frame
math, and viewport math.

Canonical names include:

- `GhostRigger.Core.Math.Transforms`
- `GhostRigger.Core.Math`
- `GhostRigger.Core.Math.Pivots`
- `GhostRigger.Core.Math.Projection`
- `GhostRigger.Core.Math.Skinning`

### Rendering

Renderer-neutral rendering contracts, render state, materials, texture upload
policy, renderer resources, backend interfaces, and backend implementations
belong under Rendering.

Canonical names include:

- `GhostRigger.Core.Rendering`
- `GhostRigger.Core.Rendering.Materials`
- `GhostRigger.Core.Rendering.Textures`
- `GhostRigger.Core.Rendering.Backends.ModernGL`
- `GhostRigger.Core.Rendering.Backends.D3D12`
- `GhostRigger.Core.Rendering.Backends.Null`

`GhostRigger.Core.Rendering.Contracts` and
`GhostRigger.Core.Rendering.Backends.*` are canonical native names when a real
renderer-neutral contract or renderer backend runtime boundary exists.

### Validation

Validation rules, model checks, resource checks, scene checks, export gates, and
comparison reports belong under Validation.

Canonical names include:

- `GhostRigger.Core.Validation`
- `GhostRigger.Core.Validation.MDL`
- `GhostRigger.Core.Validation.Scene`
- `GhostRigger.Core.Validation.Export`
- `GhostRigger.Core.Validation.Resources`

### Qt And Bridge

Technology-specific glue belongs under Adapters: Qt adapters, GPU adapters,
filesystem adapters, native host bridges, Python/C++ bridges, renderer
adapters, and external-library wrappers. Adapters connect GhostRigger to
external runtimes and must not own durable domain policy.

Canonical names include:

- `GhostRigger.Core.Qt`
- `GhostRigger.Core.Rendering.GPU`
- `GhostRigger.Core.IO.File.Write`
- `GhostRigger.Core.Bridge.NativeHost`
- `GhostRigger.Core.Bridge`

### Runtime / Native Host

Native runtime, ABI, lifecycle, diagnostics, retained handles, host services,
and C/C++ bridge surfaces belong under Runtime or Native Core ownership.

Canonical names include:

- `GhostRigger.Runtime.Core.Host`
- `GhostRigger.Native.Core.Diagnostics`
- `GhostRigger.Native.Core.Math`
- `GhostRigger.Native.Core.HostIntegration`

### Project / Session

Project files, user sessions, workspace state, recent files, project settings,
dirty-state policy, and save/load workflow ownership belong under Project or
Session.

Canonical names include:

- `GhostRigger.Core.Project`
- `GhostRigger.Core.Project.KMAX`
- `GhostRigger.Core.Project.KMAP`
- `GhostRigger.Core.Session`

### Workflow / Systems

Reusable multi-step workflows that are not just one tool and not just GUI
belong under Systems or Workflow. Use Systems when the behavior is a reusable
pipeline; use Tools when it is a user-facing product surface.

Canonical names include:

- `GhostRigger.Core.Workflow.Import`
- `GhostRigger.Core.Workflow.Export`
- `GhostRigger.Core.Workflow.Retargeting`
- `GhostRigger.Core.Tools.BAS`
- `GhostRigger.Systems.ModelPipeline`

## Merge Rules

- Merge packages that only differ by naming but share the same owner.
- Merge diagnostic-only or boundary-only packages when they no longer justify a
  separate project.
- Merge duplicate GUI, IO, Tool, Adapter, Resource, Format, Validation, Math,
  Rendering, or Scene packages into the canonical owner.
- Do not keep a package only because it already exists.
- Do not split a package unless it has a real ownership, runtime, ABI,
  dependency, or deployment reason.
- Preserve separate native projects only when there is a real binary or package
  boundary.
- Remove stale compatibility paths when possible. Keep tiny compatibility shims
  only when they protect active callers during a planned migration.

## Change Procedure

Before changing code:

1. Search for existing owners with `rg`.
2. Identify the correct canonical owner from this document.
3. Decide whether the package should move, merge, stay, or become a
   compatibility shim.
4. Keep changes focused by subsystem.
5. Keep dependency direction clean.

After changing code:

1. Update imports and package registry entries.
2. Update native payload manifests when Python payload files move.
3. Regenerate payload copies when canonical Python files packaged into native
   DLLs change.
4. Update tests/contracts for package ownership.
5. Run targeted verification only.
6. Update `CHANGES.md` with date, `Owner: LordVaderCW`, affected packages,
   summary, and verification.
