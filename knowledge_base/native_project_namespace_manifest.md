# GhostRigger Native Project Namespace Manifest

Owner: LordVaderCW
Date: 2026-06-14
Scope: Phase 1 audit snapshot. Superseded as naming authority by
`knowledge_base/package_ownership_model.md`.

## Audit Summary

- Real C++ projects in `GhostRigger.sln`: 94
- Solution-folder projects in `GhostRigger.sln`: 0
- Expected real project count: 94
- Rename status: Native, Runtime host, Renderer, Domain, GUI Boundary, and Tools Workflow batches applied; remaining rows are pending.
- Authority status: this table records current and historical Visual Studio
  project names. It must not be used as the target model when it conflicts with
  `knowledge_base/package_ownership_model.md`.
- Compatibility note: rows such as `GhostRigger.Core.GUI.Display.*`,
  `GhostRigger.Core.Rendering.Textures`, and broad GUI
  category packages describe current build state or old rename batches. Future
  package work must target the canonical owners: `GhostRigger.Core.Rendering.*`,
  `GhostRigger.Core.GUI.Display.*`, `GhostRigger.Core.GUI.Helpers.*`,
  `GhostRigger.Core.Formats.*`, `GhostRigger.Core.Resources.*`,
  `GhostRigger.Core.IO.*`, `GhostRigger.Core.Automation.*`,
  `GhostRigger.Core.Scene.*`, `GhostRigger.Core.Math.*`,
  `GhostRigger.Core.Validation.*`, `GhostRigger.Core.Project.*`,
  `GhostRigger.Core.Session`, `GhostRigger.Core.Workflow.*`,
  `GhostRigger.Systems.*`, and `GhostRigger.Adapters.*`.
- Rename rule: do not change one manifest row by itself. A native package
  rename or merge must update directories, `.vcxproj` files, filters,
  `GhostRigger.sln`, payload manifests, resource scripts, package registry
  entries, tests, and compatibility shims in one focused batch.
- Blocking anomalies:
  - `GhostRigger.Selection` is present in the requested target map but is not present in the actual solution.
  - `GhostRigger.Tools.NodeSkeletonBrowser` is present in the requested target map, but the actual solution project is `GhostRigger.Tools.NodesSkeletonBrowser`.
  - The prompt map omits actual projects `GhostRigger.Native`, `GhostRigger.Skeleton`, and `GhostRigger.Core.Tools.SequenceEditor`; proposed canonical targets are included below so the manifest covers all 94 projects.

## Missing / Corrected Project Reasons

| OldProjectName | NewProjectName | Reason |
| --- | --- | --- |
| `GhostRigger.Native` | `GhostRigger.Native.Core.Host` | Native C++ executable host for the embedded Python/Qt application and Visual Studio Debug target. |
| `GhostRigger.Skeleton` | `GhostRigger.Core.Scene.Skeleton` | Headless skeleton domain package owning skeleton builder/data contracts. |
| `GhostRigger.Core.Tools.SequenceEditor` | `GhostRigger.Core.Tools.SequenceEditor` | Merged into the canonical native SequenceEditor tool surface. |
| `GhostRigger.Tools.NodesSkeletonBrowser` | `GhostRigger.Core.Tools.NodeSkeletonBrowser` | Actual solution spelling uses `NodesSkeletonBrowser`; canonical workflow name should use the requested singular `NodeSkeletonBrowser`. |

## Project Manifest

| OldProjectName | NewProjectName | Group | Type | ModuleName | ProjectFile | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `GhostRigger.Native` | `GhostRigger.Native.Core.Host` | Native | Core | Host | `native\GhostRigger.Native.Core.Host\GhostRigger.Native.Core.Host.vcxproj` | renamed in Native batch; missing from requested map |
| `GhostRigger.Native.Core.Foundation` | `GhostRigger.Native.Core.Foundation` | Native | Core | Foundation | `native\GhostRigger.Native.Core.Foundation\GhostRigger.Native.Core.Foundation.vcxproj` | renamed in Native batch |
| `GhostRigger.Native.Core.Diagnostics` | `GhostRigger.Native.Core.Diagnostics` | Native | Core | Diagnostics | `native\GhostRigger.Native.Core.Diagnostics\GhostRigger.Native.Core.Diagnostics.vcxproj` | renamed in Native batch |
| `GhostRigger.Native.Core.Math` | `GhostRigger.Native.Core.Math` | Native | Core | Math | `native\GhostRigger.Native.Core.Math\GhostRigger.Native.Core.Math.vcxproj` | renamed in Native batch |
| `GhostRigger.Runtime` | `GhostRigger.Runtime.Core.Host` | Runtime | Core | Host | `native\GhostRigger.Runtime.Core.Host\GhostRigger.Runtime.Core.Host.vcxproj` | renamed in Runtime batch |
| `GhostRigger.Runtime.Shared.Contracts` | `GhostRigger.Runtime.Shared.Contracts` | Runtime | Shared | Contracts | `native\GhostRigger.Runtime.Shared.Contracts\GhostRigger.Runtime.Shared.Contracts.vcxproj` | already canonical |
| `GhostRigger.Runtime.Shared.Descriptors` | `GhostRigger.Runtime.Shared.Descriptors` | Runtime | Shared | Descriptors | `native\GhostRigger.Runtime.Shared.Descriptors\GhostRigger.Runtime.Shared.Descriptors.vcxproj` | already canonical |
| `GhostRigger.Runtime.Shared.Resources` | `GhostRigger.Runtime.Shared.Resources` | Runtime | Shared | Resources | `native\GhostRigger.Runtime.Shared.Resources\GhostRigger.Runtime.Shared.Resources.vcxproj` | already canonical |
| `GhostRigger.Core.Rendering.Contracts` | `GhostRigger.Core.Rendering.Contracts` | Renderer | Shared | Contracts | `native\GhostRigger.Core.Rendering.Contracts\GhostRigger.Core.Rendering.Contracts.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Core.Rendering.D3D12` | `GhostRigger.Core.Rendering.Backends.D3D12` | Renderer | Backend | D3D12 | `native\GhostRigger.Core.Rendering.Backends.D3D12\GhostRigger.Core.Rendering.Backends.D3D12.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Core.Rendering.ModernGL` | `GhostRigger.Core.Rendering.Backends.ModernGL` | Renderer | Backend | ModernGL | `native\GhostRigger.Core.Rendering.Backends.ModernGL\GhostRigger.Core.Rendering.Backends.ModernGL.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Core.Rendering.Null` | `GhostRigger.Core.Rendering.Backends.Null` | Renderer | Backend | Null | `native\GhostRigger.Core.Rendering.Backends.Null\GhostRigger.Core.Rendering.Backends.Null.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Core.Rendering.PyGFX` | `GhostRigger.Core.Rendering.Backends.PyGFX` | Renderer | Backend | PyGFX | `native\GhostRigger.Core.Rendering.Backends.PyGFX\GhostRigger.Core.Rendering.Backends.PyGFX.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Tools.BodyAttachmentSystem` | `GhostRigger.Core.Tools.BAS` | Tools | Workflow | BAS | `native\GhostRigger.Core.Tools.BAS\GhostRigger.Core.Tools.BAS.vcxproj` | renamed in BAS merge |
| `GhostRigger.Tools.Camera` | `GhostRigger.Core.Tools.Camera` | Tools | Workflow | Camera | `native\GhostRigger.Core.Tools.Camera\GhostRigger.Core.Tools.Camera.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.CharacterBuilder` | `GhostRigger.Core.Tools.CharacterBuilder` | Tools | Workflow | CharacterBuilder | `native\GhostRigger.Core.Tools.CharacterBuilder\GhostRigger.Core.Tools.CharacterBuilder.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.ContentBrowser` | `GhostRigger.Core.Tools.ContentBrowser` | Tools | Workflow | ContentBrowser | `native\GhostRigger.Core.Tools.ContentBrowser\GhostRigger.Core.Tools.ContentBrowser.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Export` | `GhostRigger.Core.Tools.Export` | Tools | Workflow | Export | `native\GhostRigger.Core.Tools.Export\GhostRigger.Core.Tools.Export.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Lighting` | `GhostRigger.Core.Tools.Lighting` | Tools | Workflow | Lighting | `native\GhostRigger.Core.Tools.Lighting\GhostRigger.Core.Tools.Lighting.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.ModuleMeshes` | `GhostRigger.Core.Tools.ModuleMeshes` | Tools | Workflow | ModuleMeshes | `native\GhostRigger.Core.Tools.ModuleMeshes\GhostRigger.Core.Tools.ModuleMeshes.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.NodesSkeletonBrowser` | `GhostRigger.Core.Tools.NodeSkeletonBrowser` | Tools | Workflow | NodeSkeletonBrowser | `native\GhostRigger.Core.Tools.NodeSkeletonBrowser\GhostRigger.Core.Tools.NodeSkeletonBrowser.vcxproj` | renamed in Tools Workflow batch; spelling mismatch in requested map |
| `GhostRigger.Tools.PivotControls` | `GhostRigger.Core.Tools.PivotControls` | Tools | Workflow | PivotControls | `native\GhostRigger.Core.Tools.PivotControls\GhostRigger.Core.Tools.PivotControls.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Properties` | `GhostRigger.Core.Tools.Properties` | Tools | Workflow | Properties | `native\GhostRigger.Core.Tools.Properties\GhostRigger.Core.Tools.Properties.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.ResourceBrowser` | `GhostRigger.Core.Tools.ResourceBrowser` | Tools | Workflow | ResourceBrowser | `native\GhostRigger.Core.Tools.ResourceBrowser\GhostRigger.Core.Tools.ResourceBrowser.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Retargeting` | `GhostRigger.Core.Tools.Retargeting` | Tools | Workflow | Retargeting | `native\GhostRigger.Core.Tools.Retargeting\GhostRigger.Core.Tools.Retargeting.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.SceneInformation` | `GhostRigger.Core.Tools.SceneInformation` | Tools | Workflow | SceneInformation | `native\GhostRigger.Core.Tools.SceneInformation\GhostRigger.Core.Tools.SceneInformation.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.SequenceEditor` | `GhostRigger.Core.Tools.SequenceEditor` | Tools | Workflow | SequenceEditor | `native\GhostRigger.Core.Tools.SequenceEditor\GhostRigger.Core.Tools.SequenceEditor.vcxproj` | renamed in Sequence merge |
| `GhostRigger.Tools.SpriteMaterials` | `GhostRigger.Core.Tools.SpriteMaterials` | Tools | Workflow | SpriteMaterials | `native\GhostRigger.Core.Tools.SpriteMaterials\GhostRigger.Core.Tools.SpriteMaterials.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.TwoDABrowser` | `GhostRigger.Core.Tools.TwoDABrowser` | Tools | Workflow | TwoDABrowser | `native\GhostRigger.Core.Tools.TwoDABrowser\GhostRigger.Core.Tools.TwoDABrowser.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Core.Tools.Retargeting.Workbench` | `GhostRigger.Core.Tools.Retargeting.Workbench` | Windows | Workbench | AnimationRetarget | `native\GhostRigger.Core.Tools.Retargeting.Workbench\GhostRigger.Core.Tools.Retargeting.Workbench.vcxproj` | renamed in Windows batch |
| `GhostRigger.Core.Tools.Rigging` | `GhostRigger.Core.Tools.Rigging` | Windows | Legacy | Rigging | `native\GhostRigger.Core.Tools.Rigging\GhostRigger.Core.Tools.Rigging.vcxproj` | renamed in Windows batch |
| `GhostRigger.Core.Tools.ModuleEditor` | `GhostRigger.Core.Tools.ModuleEditor` | Windows | Editor | Level | `native\GhostRigger.Core.Tools.ModuleEditor\GhostRigger.Core.Tools.ModuleEditor.vcxproj` | renamed in Windows batch |
| `GhostRigger.Core.GUI.Display.Shell.Main` | `GhostRigger.Core.GUI.Display.Shell.Main` | Windows | Shell | Main | `native\GhostRigger.Core.GUI.Display.Shell.Main\GhostRigger.Core.GUI.Display.Shell.Main.vcxproj` | renamed in Windows batch |
| `GhostRigger.Core.Tools.UnrealAnimator` | `GhostRigger.Core.Tools.UnrealAnimator` | Windows | Workbench | UnrealAnimator | `native\GhostRigger.Core.Tools.UnrealAnimator\GhostRigger.Core.Tools.UnrealAnimator.vcxproj` | renamed in Windows batch |
| `GhostRigger.Animation` | `GhostRigger.Core.Workflow.Animation` | Domain | Core | Animation | `native\GhostRigger.Core.Workflow.Animation\GhostRigger.Core.Workflow.Animation.vcxproj` | renamed in Domain batch |
| `GhostRigger.AnimationRetargeting` | `GhostRigger.Core.Workflow.AnimationRetargeting` | Domain | Core | AnimationRetargeting | `native\GhostRigger.Core.Workflow.AnimationRetargeting\GhostRigger.Core.Workflow.AnimationRetargeting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Assets` | `GhostRigger.Core.Resources.Assets` | Domain | Core | Assets | `native\GhostRigger.Core.Resources.Assets\GhostRigger.Core.Resources.Assets.vcxproj` | renamed in Domain batch |
| `GhostRigger.Autorig` | `GhostRigger.Core.Workflow.Autorig` | Domain | Core | Autorig | `native\GhostRigger.Core.Workflow.Autorig\GhostRigger.Core.Workflow.Autorig.vcxproj` | renamed in Domain batch |
| `GhostRigger.Camera` | `GhostRigger.Core.Math.Camera` | Domain | Core | Camera | `native\GhostRigger.Core.Math.Camera\GhostRigger.Core.Math.Camera.vcxproj` | renamed in Domain batch |
| `GhostRigger.Characters` | `GhostRigger.Core.Workflow.Characters` | Domain | Core | Characters | `native\GhostRigger.Core.Workflow.Characters\GhostRigger.Core.Workflow.Characters.vcxproj` | renamed in Domain batch |
| `GhostRigger.Converters` | `GhostRigger.Core.IO.Conversion` | Domain | Core | Converters | `native\GhostRigger.Core.IO.Conversion\GhostRigger.Core.IO.Conversion.vcxproj` | renamed in Domain batch |
| `GhostRigger.Diagnostics` | `GhostRigger.Runtime.Core.Diagnostics` | Domain | Core | Diagnostics | `native\GhostRigger.Runtime.Core.Diagnostics\GhostRigger.Runtime.Core.Diagnostics.vcxproj` | renamed in Domain batch |
| `GhostRigger.Export` | `GhostRigger.Core.IO.Export` | Domain | Core | Export | `native\GhostRigger.Core.IO.Export\GhostRigger.Core.IO.Export.vcxproj` | renamed in Domain batch |
| `GhostRigger.Formats` | `GhostRigger.Core.IO.Serialization.GFF` | Domain | Core | Formats | `native\GhostRigger.Core.IO.Serialization.GFF\GhostRigger.Core.IO.Serialization.GFF.vcxproj` | renamed in Domain batch |
| `GhostRigger.Game` | `GhostRigger.Core.Resources.Game` | Domain | Core | Game | `native\GhostRigger.Core.Resources.Game\GhostRigger.Core.Resources.Game.vcxproj` | renamed in Domain batch |
| `GhostRigger.GameLibrary` | `GhostRigger.Core.Resources.GameLibrary` | Domain | Core | GameLibrary | `native\GhostRigger.Core.Resources.GameLibrary\GhostRigger.Core.Resources.GameLibrary.vcxproj` | renamed in Domain batch |
| `GhostRigger.Geometry` | `GhostRigger.Core.Math.Geometry` | Domain | Core | Geometry | `native\GhostRigger.Core.Math.Geometry\GhostRigger.Core.Math.Geometry.vcxproj` | renamed in Domain batch |
| `GhostRigger.Gizmo` | `GhostRigger.Core.GUI.Helpers.Gizmo` | Domain | Core | Gizmo | `native\GhostRigger.Core.GUI.Helpers.Gizmo\GhostRigger.Core.GUI.Helpers.Gizmo.vcxproj` | renamed in Domain batch |
| `GhostRigger.Graphics` | `GhostRigger.Core.Rendering.Textures` | Domain | Core | Graphics | `native\GhostRigger.Core.Rendering.Textures\GhostRigger.Core.Rendering.Textures.vcxproj` | renamed in Domain batch |
| `GhostRigger.Infra` | `GhostRigger.Runtime.Core.Infrastructure` | Domain | Core | Infrastructure | `native\GhostRigger.Runtime.Core.Infrastructure\GhostRigger.Runtime.Core.Infrastructure.vcxproj` | renamed in Domain batch |
| `GhostRigger.IO` | `GhostRigger.Core.IO.FBX` | Domain | Core | IO | `native\GhostRigger.Core.IO.FBX\GhostRigger.Core.IO.FBX.vcxproj` | renamed in Domain batch |
| `GhostRigger.IPC` | `GhostRigger.Core.Automation.IPC` | Domain | Core | IPC | `native\GhostRigger.Core.Automation.IPC\GhostRigger.Core.Automation.IPC.vcxproj` | renamed in Domain batch |
| `GhostRigger.KotorMCP` | `GhostRigger.Core.Automation.MCP` | Domain | Core | KotorMCP | `native\GhostRigger.Core.Automation.MCP\GhostRigger.Core.Automation.MCP.vcxproj` | renamed in Domain batch |
| `GhostRigger.Level` | `GhostRigger.Core.Scene.Level` | Domain | Core | Level | `native\GhostRigger.Core.Scene.Level\GhostRigger.Core.Scene.Level.vcxproj` | renamed in Domain batch |
| `GhostRigger.Lighting` | `GhostRigger.Core.Rendering.Lighting` | Domain | Core | Lighting | `native\GhostRigger.Core.Rendering.Lighting\GhostRigger.Core.Rendering.Lighting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Math` | `GhostRigger.Core.Math` | Domain | Core | Math | `native\GhostRigger.Core.Math\GhostRigger.Core.Math.vcxproj` | renamed in Domain batch |
| `GhostRigger.MDL` | `GhostRigger.Core.IO.MDL` | Domain | Core | MDL | `native\GhostRigger.Core.IO.MDL\GhostRigger.Core.IO.MDL.vcxproj` | renamed in Domain batch |
| `GhostRigger.Measurement` | `GhostRigger.Core.Math.Measurement` | Domain | Core | Measurement | `native\GhostRigger.Core.Math.Measurement\GhostRigger.Core.Math.Measurement.vcxproj` | renamed in Domain batch |
| `GhostRigger.MeshTools` | `GhostRigger.Core.Tools.Mesh` | Domain | Core | MeshTools | `native\GhostRigger.Core.Tools.Mesh\GhostRigger.Core.Tools.Mesh.vcxproj` | renamed in Domain batch |
| `GhostRigger.Modules` | `GhostRigger.Core.Scene.Modules` | Domain | Core | Modules | `native\GhostRigger.Core.Scene.Modules\GhostRigger.Core.Scene.Modules.vcxproj` | renamed in Domain batch |
| `GhostRigger.Ports` | `GhostRigger.Core.Rendering.Ports` | Domain | Core | Ports | `native\GhostRigger.Core.Rendering.Ports\GhostRigger.Core.Rendering.Ports.vcxproj` | renamed in Domain batch |
| `GhostRigger.Project` | `GhostRigger.Core.Project` | Domain | Core | Project | `native\GhostRigger.Core.Project\GhostRigger.Core.Project.vcxproj` | renamed in Domain batch |
| `GhostRigger.Rendering` | `GhostRigger.Core.Rendering` | Domain | Core | Rendering | `native\GhostRigger.Core.Rendering\GhostRigger.Core.Rendering.vcxproj` | renamed in Domain batch |
| `GhostRigger.Resources` | `GhostRigger.Core.Resources` | Domain | Core | Resources | `native\GhostRigger.Core.Resources\GhostRigger.Core.Resources.vcxproj` | renamed in Domain batch |
| `GhostRigger.Retargeting` | `GhostRigger.Core.Workflow.Retargeting` | Domain | Core | Retargeting | `native\GhostRigger.Core.Workflow.Retargeting\GhostRigger.Core.Workflow.Retargeting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Scene` | `GhostRigger.Core.Scene` | Domain | Core | Scene | `native\GhostRigger.Core.Scene\GhostRigger.Core.Scene.vcxproj` | renamed in Domain batch |
| `GhostRigger.Core.Tools.SequenceEditor` | `GhostRigger.Core.Tools.SequenceEditor` | Domain | Core | Sequence | `native\GhostRigger.Core.Tools.SequenceEditor\GhostRigger.Core.Tools.SequenceEditor.vcxproj` | renamed in Sequence merge; retired from solution |
| `GhostRigger.Skeleton` | `GhostRigger.Core.Scene.Skeleton` | Domain | Core | Skeleton | `native\GhostRigger.Core.Scene.Skeleton\GhostRigger.Core.Scene.Skeleton.vcxproj` | renamed in Domain batch; missing from requested map |
| `GhostRigger.Special` | `GhostRigger.Core.Tools.Special` | Domain | Core | Special | `native\GhostRigger.Core.Tools.Special\GhostRigger.Core.Tools.Special.vcxproj` | renamed in Domain batch |
| `GhostRigger.Templates` | `GhostRigger.Core.Formats.TwoDA` | Domain | Core | Templates | `native\GhostRigger.Core.Formats.TwoDA\GhostRigger.Core.Formats.TwoDA.vcxproj` | renamed in Domain batch |
| `GhostRigger.Unreal` | `GhostRigger.Adapters.Unreal` | Domain | Core | Unreal | `native\GhostRigger.Adapters.Unreal\GhostRigger.Adapters.Unreal.vcxproj` | renamed in Domain batch |
| `GhostRigger.Validation` | `GhostRigger.Core.Validation` | Domain | Core | Validation | `native\GhostRigger.Core.Validation\GhostRigger.Core.Validation.vcxproj` | renamed in Domain batch |
| `GhostRigger.Walkmesh` | `GhostRigger.Core.Scene.Walkmesh` | Domain | Core | Walkmesh | `native\GhostRigger.Core.Scene.Walkmesh\GhostRigger.Core.Scene.Walkmesh.vcxproj` | renamed in Domain batch |
| `GhostRigger.Workbench` | `GhostRigger.Core.Tools.Workbench` | Domain | Core | Workbench | `native\GhostRigger.Core.Tools.Workbench\GhostRigger.Core.Tools.Workbench.vcxproj` | renamed in Domain batch |
| `GhostRigger.Workflow` | `GhostRigger.Core.Workflow` | Domain | Core | Workflow | `native\GhostRigger.Core.Workflow\GhostRigger.Core.Workflow.vcxproj` | renamed in Domain batch |
| `GhostRigger.GUI.Camera` | `GhostRigger.Core.GUI.Display.Camera` | GUI | Boundary | Camera | `native\GhostRigger.Core.GUI.Display.Camera\GhostRigger.Core.GUI.Display.Camera.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Dialogs` | `GhostRigger.Core.GUI.Display.Dialogs` | GUI | Boundary | Dialogs | `native\GhostRigger.Core.GUI.Display.Dialogs\GhostRigger.Core.GUI.Display.Dialogs.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Gizmo` | `GhostRigger.Core.GUI.Display.Overlays.Gizmo` | GUI | Boundary | Gizmo | `native\GhostRigger.Core.GUI.Display.Overlays.Gizmo\GhostRigger.Core.GUI.Display.Overlays.Gizmo.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Integration` | `GhostRigger.Core.GUI.Display.Integration` | GUI | Boundary | Integration | `native\GhostRigger.Core.GUI.Display.Integration\GhostRigger.Core.GUI.Display.Integration.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Lighting` | `GhostRigger.Core.GUI.Display.Lighting` | GUI | Boundary | Lighting | `native\GhostRigger.Core.GUI.Display.Lighting\GhostRigger.Core.GUI.Display.Lighting.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Panels` | `GhostRigger.Core.GUI.Display.Panels` | GUI | Boundary | Panels | `native\GhostRigger.Core.GUI.Display.Panels\GhostRigger.Core.GUI.Display.Panels.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Rendering` | `GhostRigger.Core.GUI.Display.Rendering` | GUI | Boundary | Rendering | `native\GhostRigger.Core.GUI.Display.Rendering\GhostRigger.Core.GUI.Display.Rendering.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.SequenceEditor` | `GhostRigger.Core.GUI.Display.SequenceEditor` | GUI | Boundary | SequenceEditor | `native\GhostRigger.Core.GUI.Display.SequenceEditor\GhostRigger.Core.GUI.Display.SequenceEditor.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Textures` | `GhostRigger.Core.GUI.Display.Textures` | GUI | Boundary | Textures | `native\GhostRigger.Core.GUI.Display.Textures\GhostRigger.Core.GUI.Display.Textures.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Theme` | `GhostRigger.Core.GUI.Display.Theme` | GUI | Boundary | Theme | `native\GhostRigger.Core.GUI.Display.Theme\GhostRigger.Core.GUI.Display.Theme.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Viewports` | `GhostRigger.Core.GUI.Display.Viewports` | GUI | Boundary | Viewports | `native\GhostRigger.Core.GUI.Display.Viewports\GhostRigger.Core.GUI.Display.Viewports.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.Adapters.Files` | `GhostRigger.Adapters.Files` | Adapters | IO | Files | `native\GhostRigger.Adapters.Files\GhostRigger.Adapters.Files.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.GPU` | `GhostRigger.Adapters.GPU` | Adapters | Hardware | GPU | `native\GhostRigger.Adapters.GPU\GhostRigger.Adapters.GPU.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtAutorig` | `GhostRigger.Adapters.Qt.Autorig` | Adapters | Qt | Autorig | `native\GhostRigger.Adapters.Qt.Autorig\GhostRigger.Adapters.Qt.Autorig.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtIPC` | `GhostRigger.Adapters.Qt.IPC` | Adapters | Qt | IPC | `native\GhostRigger.Adapters.Qt.IPC\GhostRigger.Adapters.Qt.IPC.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtViewport` | `GhostRigger.Adapters.Qt.Viewport` | Adapters | Qt | Viewport | `native\GhostRigger.Adapters.Qt.Viewport\GhostRigger.Adapters.Qt.Viewport.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.Rendering` | `GhostRigger.Adapters.Rendering` | Adapters | Rendering | Core | `native\GhostRigger.Adapters.Rendering\GhostRigger.Adapters.Rendering.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.Scripts` | `GhostRigger.Adapters.Scripting` | Adapters | Scripting | Core | `native\GhostRigger.Adapters.Scripting\GhostRigger.Adapters.Scripting.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Core.Tools.BAS` | `GhostRigger.Core.Tools.BAS` | Systems | Feature | BAS | `native\GhostRigger.Core.Tools.BAS\GhostRigger.Core.Tools.BAS.vcxproj` | renamed in BAS merge; retired from solution |
