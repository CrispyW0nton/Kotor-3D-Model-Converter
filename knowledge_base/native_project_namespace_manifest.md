# GhostRigger Native Project Namespace Manifest

Owner: LordVaderCW
Date: 2026-06-14
Scope: Phase 1 audit for canonical `GhostRigger.Group.Type.ModuleName` project naming.

## Audit Summary

- Real C++ projects in `GhostRigger.sln`: 94
- Solution-folder projects in `GhostRigger.sln`: 0
- Expected real project count: 94
- Rename status: Native, Runtime host, Renderer, Domain, GUI Boundary, and Tools Workflow batches applied; remaining rows are pending.
- Blocking anomalies:
  - `GhostRigger.Selection` is present in the requested target map but is not present in the actual solution.
  - `GhostRigger.Tools.NodeSkeletonBrowser` is present in the requested target map, but the actual solution project is `GhostRigger.Tools.NodesSkeletonBrowser`.
  - The prompt map omits actual projects `GhostRigger.Native`, `GhostRigger.Skeleton`, and `GhostRigger.Sequence`; proposed canonical targets are included below so the manifest covers all 94 projects.

## Missing / Corrected Project Reasons

| OldProjectName | NewProjectName | Reason |
| --- | --- | --- |
| `GhostRigger.Native` | `GhostRigger.Native.Core.Host` | Native C++ executable host for the embedded Python/Qt application and Visual Studio Debug target. |
| `GhostRigger.Skeleton` | `GhostRigger.Domain.Core.Skeleton` | Headless skeleton domain package owning skeleton builder/data contracts. |
| `GhostRigger.Sequence` | `GhostRigger.Domain.Core.Sequence` | Headless sequence domain package owning sequence assets, tracks, playback, evaluation, and serialization. |
| `GhostRigger.Tools.NodesSkeletonBrowser` | `GhostRigger.Tools.Workflow.NodeSkeletonBrowser` | Actual solution spelling uses `NodesSkeletonBrowser`; canonical workflow name should use the requested singular `NodeSkeletonBrowser`. |

## Project Manifest

| OldProjectName | NewProjectName | Group | Type | ModuleName | ProjectFile | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `GhostRigger.Native` | `GhostRigger.Native.Core.Host` | Native | Core | Host | `native\GhostRigger.Native.Core.Host\GhostRigger.Native.Core.Host.vcxproj` | renamed in Native batch; missing from requested map |
| `GhostRigger.Native.NativeCore` | `GhostRigger.Native.Core.Foundation` | Native | Core | Foundation | `native\GhostRigger.Native.Core.Foundation\GhostRigger.Native.Core.Foundation.vcxproj` | renamed in Native batch |
| `GhostRigger.Native.NativeCore.Diagnostics` | `GhostRigger.Native.Core.Diagnostics` | Native | Core | Diagnostics | `native\GhostRigger.Native.Core.Diagnostics\GhostRigger.Native.Core.Diagnostics.vcxproj` | renamed in Native batch |
| `GhostRigger.Native.NativeCore.Math` | `GhostRigger.Native.Core.Math` | Native | Core | Math | `native\GhostRigger.Native.Core.Math\GhostRigger.Native.Core.Math.vcxproj` | renamed in Native batch |
| `GhostRigger.Runtime` | `GhostRigger.Runtime.Core.Host` | Runtime | Core | Host | `native\GhostRigger.Runtime.Core.Host\GhostRigger.Runtime.Core.Host.vcxproj` | renamed in Runtime batch |
| `GhostRigger.Runtime.Shared.Contracts` | `GhostRigger.Runtime.Shared.Contracts` | Runtime | Shared | Contracts | `native\GhostRigger.Runtime.Shared.Contracts\GhostRigger.Runtime.Shared.Contracts.vcxproj` | already canonical |
| `GhostRigger.Runtime.Shared.Descriptors` | `GhostRigger.Runtime.Shared.Descriptors` | Runtime | Shared | Descriptors | `native\GhostRigger.Runtime.Shared.Descriptors\GhostRigger.Runtime.Shared.Descriptors.vcxproj` | already canonical |
| `GhostRigger.Runtime.Shared.Resources` | `GhostRigger.Runtime.Shared.Resources` | Runtime | Shared | Resources | `native\GhostRigger.Runtime.Shared.Resources\GhostRigger.Runtime.Shared.Resources.vcxproj` | already canonical |
| `GhostRigger.Renderer.Contracts` | `GhostRigger.Renderer.Shared.Contracts` | Renderer | Shared | Contracts | `native\GhostRigger.Renderer.Shared.Contracts\GhostRigger.Renderer.Shared.Contracts.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Renderer.D3D12` | `GhostRigger.Renderer.Backend.D3D12` | Renderer | Backend | D3D12 | `native\GhostRigger.Renderer.Backend.D3D12\GhostRigger.Renderer.Backend.D3D12.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Renderer.ModernGL` | `GhostRigger.Renderer.Backend.ModernGL` | Renderer | Backend | ModernGL | `native\GhostRigger.Renderer.Backend.ModernGL\GhostRigger.Renderer.Backend.ModernGL.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Renderer.Null` | `GhostRigger.Renderer.Backend.Null` | Renderer | Backend | Null | `native\GhostRigger.Renderer.Backend.Null\GhostRigger.Renderer.Backend.Null.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Renderer.PyGFX` | `GhostRigger.Renderer.Backend.PyGFX` | Renderer | Backend | PyGFX | `native\GhostRigger.Renderer.Backend.PyGFX\GhostRigger.Renderer.Backend.PyGFX.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Tools.BodyAttachmentSystem` | `GhostRigger.Tools.Workflow.BodyAttachmentSystem` | Tools | Workflow | BodyAttachmentSystem | `native\GhostRigger.Tools.Workflow.BodyAttachmentSystem\GhostRigger.Tools.Workflow.BodyAttachmentSystem.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Camera` | `GhostRigger.Tools.Workflow.Camera` | Tools | Workflow | Camera | `native\GhostRigger.Tools.Workflow.Camera\GhostRigger.Tools.Workflow.Camera.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.CharacterBuilder` | `GhostRigger.Tools.Workflow.CharacterBuilder` | Tools | Workflow | CharacterBuilder | `native\GhostRigger.Tools.Workflow.CharacterBuilder\GhostRigger.Tools.Workflow.CharacterBuilder.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.ContentBrowser` | `GhostRigger.Tools.Workflow.ContentBrowser` | Tools | Workflow | ContentBrowser | `native\GhostRigger.Tools.Workflow.ContentBrowser\GhostRigger.Tools.Workflow.ContentBrowser.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Export` | `GhostRigger.Tools.Workflow.Export` | Tools | Workflow | Export | `native\GhostRigger.Tools.Workflow.Export\GhostRigger.Tools.Workflow.Export.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Lighting` | `GhostRigger.Tools.Workflow.Lighting` | Tools | Workflow | Lighting | `native\GhostRigger.Tools.Workflow.Lighting\GhostRigger.Tools.Workflow.Lighting.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.ModuleMeshes` | `GhostRigger.Tools.Workflow.ModuleMeshes` | Tools | Workflow | ModuleMeshes | `native\GhostRigger.Tools.Workflow.ModuleMeshes\GhostRigger.Tools.Workflow.ModuleMeshes.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.NodesSkeletonBrowser` | `GhostRigger.Tools.Workflow.NodeSkeletonBrowser` | Tools | Workflow | NodeSkeletonBrowser | `native\GhostRigger.Tools.Workflow.NodeSkeletonBrowser\GhostRigger.Tools.Workflow.NodeSkeletonBrowser.vcxproj` | renamed in Tools Workflow batch; spelling mismatch in requested map |
| `GhostRigger.Tools.PivotControls` | `GhostRigger.Tools.Workflow.PivotControls` | Tools | Workflow | PivotControls | `native\GhostRigger.Tools.Workflow.PivotControls\GhostRigger.Tools.Workflow.PivotControls.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Properties` | `GhostRigger.Tools.Workflow.Properties` | Tools | Workflow | Properties | `native\GhostRigger.Tools.Workflow.Properties\GhostRigger.Tools.Workflow.Properties.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.ResourceBrowser` | `GhostRigger.Tools.Workflow.ResourceBrowser` | Tools | Workflow | ResourceBrowser | `native\GhostRigger.Tools.Workflow.ResourceBrowser\GhostRigger.Tools.Workflow.ResourceBrowser.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.Retargeting` | `GhostRigger.Tools.Workflow.Retargeting` | Tools | Workflow | Retargeting | `native\GhostRigger.Tools.Workflow.Retargeting\GhostRigger.Tools.Workflow.Retargeting.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.SceneInformation` | `GhostRigger.Tools.Workflow.SceneInformation` | Tools | Workflow | SceneInformation | `native\GhostRigger.Tools.Workflow.SceneInformation\GhostRigger.Tools.Workflow.SceneInformation.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.SequenceEditor` | `GhostRigger.Tools.Workflow.SequenceEditor` | Tools | Workflow | SequenceEditor | `native\GhostRigger.Tools.Workflow.SequenceEditor\GhostRigger.Tools.Workflow.SequenceEditor.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.SpriteMaterials` | `GhostRigger.Tools.Workflow.SpriteMaterials` | Tools | Workflow | SpriteMaterials | `native\GhostRigger.Tools.Workflow.SpriteMaterials\GhostRigger.Tools.Workflow.SpriteMaterials.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Tools.TwoDABrowser` | `GhostRigger.Tools.Workflow.TwoDABrowser` | Tools | Workflow | TwoDABrowser | `native\GhostRigger.Tools.Workflow.TwoDABrowser\GhostRigger.Tools.Workflow.TwoDABrowser.vcxproj` | renamed in Tools Workflow batch |
| `GhostRigger.Windows.AnimationRetargetWorkbench` | `GhostRigger.Windows.Workbench.AnimationRetarget` | Windows | Workbench | AnimationRetarget | `native\GhostRigger.Windows.Workbench.AnimationRetarget\GhostRigger.Windows.Workbench.AnimationRetarget.vcxproj` | renamed in Windows batch |
| `GhostRigger.Windows.LegacyRiggingWindow` | `GhostRigger.Windows.Legacy.Rigging` | Windows | Legacy | Rigging | `native\GhostRigger.Windows.Legacy.Rigging\GhostRigger.Windows.Legacy.Rigging.vcxproj` | renamed in Windows batch |
| `GhostRigger.Windows.LevelEditor` | `GhostRigger.Windows.Editor.Level` | Windows | Editor | Level | `native\GhostRigger.Windows.Editor.Level\GhostRigger.Windows.Editor.Level.vcxproj` | renamed in Windows batch |
| `GhostRigger.Windows.MainWindow` | `GhostRigger.Windows.Shell.Main` | Windows | Shell | Main | `native\GhostRigger.Windows.Shell.Main\GhostRigger.Windows.Shell.Main.vcxproj` | renamed in Windows batch |
| `GhostRigger.Windows.UnrealAnimatorWindow` | `GhostRigger.Windows.Workbench.UnrealAnimator` | Windows | Workbench | UnrealAnimator | `native\GhostRigger.Windows.Workbench.UnrealAnimator\GhostRigger.Windows.Workbench.UnrealAnimator.vcxproj` | renamed in Windows batch |
| `GhostRigger.Animation` | `GhostRigger.Domain.Core.Animation` | Domain | Core | Animation | `native\GhostRigger.Domain.Core.Animation\GhostRigger.Domain.Core.Animation.vcxproj` | renamed in Domain batch |
| `GhostRigger.AnimationRetargeting` | `GhostRigger.Domain.Core.AnimationRetargeting` | Domain | Core | AnimationRetargeting | `native\GhostRigger.Domain.Core.AnimationRetargeting\GhostRigger.Domain.Core.AnimationRetargeting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Assets` | `GhostRigger.Domain.Core.Assets` | Domain | Core | Assets | `native\GhostRigger.Domain.Core.Assets\GhostRigger.Domain.Core.Assets.vcxproj` | renamed in Domain batch |
| `GhostRigger.Autorig` | `GhostRigger.Domain.Core.Autorig` | Domain | Core | Autorig | `native\GhostRigger.Domain.Core.Autorig\GhostRigger.Domain.Core.Autorig.vcxproj` | renamed in Domain batch |
| `GhostRigger.Camera` | `GhostRigger.Domain.Core.Camera` | Domain | Core | Camera | `native\GhostRigger.Domain.Core.Camera\GhostRigger.Domain.Core.Camera.vcxproj` | renamed in Domain batch |
| `GhostRigger.Characters` | `GhostRigger.Domain.Core.Characters` | Domain | Core | Characters | `native\GhostRigger.Domain.Core.Characters\GhostRigger.Domain.Core.Characters.vcxproj` | renamed in Domain batch |
| `GhostRigger.Converters` | `GhostRigger.Domain.Core.Converters` | Domain | Core | Converters | `native\GhostRigger.Domain.Core.Converters\GhostRigger.Domain.Core.Converters.vcxproj` | renamed in Domain batch |
| `GhostRigger.Diagnostics` | `GhostRigger.Domain.Core.Diagnostics` | Domain | Core | Diagnostics | `native\GhostRigger.Domain.Core.Diagnostics\GhostRigger.Domain.Core.Diagnostics.vcxproj` | renamed in Domain batch |
| `GhostRigger.Export` | `GhostRigger.Domain.Core.Export` | Domain | Core | Export | `native\GhostRigger.Domain.Core.Export\GhostRigger.Domain.Core.Export.vcxproj` | renamed in Domain batch |
| `GhostRigger.Formats` | `GhostRigger.Domain.Core.Formats` | Domain | Core | Formats | `native\GhostRigger.Domain.Core.Formats\GhostRigger.Domain.Core.Formats.vcxproj` | renamed in Domain batch |
| `GhostRigger.Game` | `GhostRigger.Domain.Core.Game` | Domain | Core | Game | `native\GhostRigger.Domain.Core.Game\GhostRigger.Domain.Core.Game.vcxproj` | renamed in Domain batch |
| `GhostRigger.GameLibrary` | `GhostRigger.Domain.Core.GameLibrary` | Domain | Core | GameLibrary | `native\GhostRigger.Domain.Core.GameLibrary\GhostRigger.Domain.Core.GameLibrary.vcxproj` | renamed in Domain batch |
| `GhostRigger.Geometry` | `GhostRigger.Domain.Core.Geometry` | Domain | Core | Geometry | `native\GhostRigger.Domain.Core.Geometry\GhostRigger.Domain.Core.Geometry.vcxproj` | renamed in Domain batch |
| `GhostRigger.Gizmo` | `GhostRigger.Domain.Core.Gizmo` | Domain | Core | Gizmo | `native\GhostRigger.Domain.Core.Gizmo\GhostRigger.Domain.Core.Gizmo.vcxproj` | renamed in Domain batch |
| `GhostRigger.Graphics` | `GhostRigger.Domain.Core.Graphics` | Domain | Core | Graphics | `native\GhostRigger.Domain.Core.Graphics\GhostRigger.Domain.Core.Graphics.vcxproj` | renamed in Domain batch |
| `GhostRigger.Infra` | `GhostRigger.Domain.Core.Infrastructure` | Domain | Core | Infrastructure | `native\GhostRigger.Domain.Core.Infrastructure\GhostRigger.Domain.Core.Infrastructure.vcxproj` | renamed in Domain batch |
| `GhostRigger.IO` | `GhostRigger.Domain.Core.IO` | Domain | Core | IO | `native\GhostRigger.Domain.Core.IO\GhostRigger.Domain.Core.IO.vcxproj` | renamed in Domain batch |
| `GhostRigger.IPC` | `GhostRigger.Domain.Core.IPC` | Domain | Core | IPC | `native\GhostRigger.Domain.Core.IPC\GhostRigger.Domain.Core.IPC.vcxproj` | renamed in Domain batch |
| `GhostRigger.KotorMCP` | `GhostRigger.Domain.Core.KotorMCP` | Domain | Core | KotorMCP | `native\GhostRigger.Domain.Core.KotorMCP\GhostRigger.Domain.Core.KotorMCP.vcxproj` | renamed in Domain batch |
| `GhostRigger.Level` | `GhostRigger.Domain.Core.Level` | Domain | Core | Level | `native\GhostRigger.Domain.Core.Level\GhostRigger.Domain.Core.Level.vcxproj` | renamed in Domain batch |
| `GhostRigger.Lighting` | `GhostRigger.Domain.Core.Lighting` | Domain | Core | Lighting | `native\GhostRigger.Domain.Core.Lighting\GhostRigger.Domain.Core.Lighting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Math` | `GhostRigger.Domain.Core.Math` | Domain | Core | Math | `native\GhostRigger.Domain.Core.Math\GhostRigger.Domain.Core.Math.vcxproj` | renamed in Domain batch |
| `GhostRigger.MDL` | `GhostRigger.Domain.Core.MDL` | Domain | Core | MDL | `native\GhostRigger.Domain.Core.MDL\GhostRigger.Domain.Core.MDL.vcxproj` | renamed in Domain batch |
| `GhostRigger.Measurement` | `GhostRigger.Domain.Core.Measurement` | Domain | Core | Measurement | `native\GhostRigger.Domain.Core.Measurement\GhostRigger.Domain.Core.Measurement.vcxproj` | renamed in Domain batch |
| `GhostRigger.MeshTools` | `GhostRigger.Domain.Core.MeshTools` | Domain | Core | MeshTools | `native\GhostRigger.Domain.Core.MeshTools\GhostRigger.Domain.Core.MeshTools.vcxproj` | renamed in Domain batch |
| `GhostRigger.Modules` | `GhostRigger.Domain.Core.Modules` | Domain | Core | Modules | `native\GhostRigger.Domain.Core.Modules\GhostRigger.Domain.Core.Modules.vcxproj` | renamed in Domain batch |
| `GhostRigger.Ports` | `GhostRigger.Domain.Core.Ports` | Domain | Core | Ports | `native\GhostRigger.Domain.Core.Ports\GhostRigger.Domain.Core.Ports.vcxproj` | renamed in Domain batch |
| `GhostRigger.Project` | `GhostRigger.Domain.Core.Project` | Domain | Core | Project | `native\GhostRigger.Domain.Core.Project\GhostRigger.Domain.Core.Project.vcxproj` | renamed in Domain batch |
| `GhostRigger.Rendering` | `GhostRigger.Domain.Core.Rendering` | Domain | Core | Rendering | `native\GhostRigger.Domain.Core.Rendering\GhostRigger.Domain.Core.Rendering.vcxproj` | renamed in Domain batch |
| `GhostRigger.Resources` | `GhostRigger.Domain.Core.Resources` | Domain | Core | Resources | `native\GhostRigger.Domain.Core.Resources\GhostRigger.Domain.Core.Resources.vcxproj` | renamed in Domain batch |
| `GhostRigger.Retargeting` | `GhostRigger.Domain.Core.Retargeting` | Domain | Core | Retargeting | `native\GhostRigger.Domain.Core.Retargeting\GhostRigger.Domain.Core.Retargeting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Scene` | `GhostRigger.Domain.Core.Scene` | Domain | Core | Scene | `native\GhostRigger.Domain.Core.Scene\GhostRigger.Domain.Core.Scene.vcxproj` | renamed in Domain batch |
| `GhostRigger.Sequence` | `GhostRigger.Domain.Core.Sequence` | Domain | Core | Sequence | `native\GhostRigger.Domain.Core.Sequence\GhostRigger.Domain.Core.Sequence.vcxproj` | renamed in Domain batch; missing from requested map |
| `GhostRigger.Skeleton` | `GhostRigger.Domain.Core.Skeleton` | Domain | Core | Skeleton | `native\GhostRigger.Domain.Core.Skeleton\GhostRigger.Domain.Core.Skeleton.vcxproj` | renamed in Domain batch; missing from requested map |
| `GhostRigger.Special` | `GhostRigger.Domain.Core.Special` | Domain | Core | Special | `native\GhostRigger.Domain.Core.Special\GhostRigger.Domain.Core.Special.vcxproj` | renamed in Domain batch |
| `GhostRigger.Templates` | `GhostRigger.Domain.Core.Templates` | Domain | Core | Templates | `native\GhostRigger.Domain.Core.Templates\GhostRigger.Domain.Core.Templates.vcxproj` | renamed in Domain batch |
| `GhostRigger.Unreal` | `GhostRigger.Domain.Core.Unreal` | Domain | Core | Unreal | `native\GhostRigger.Domain.Core.Unreal\GhostRigger.Domain.Core.Unreal.vcxproj` | renamed in Domain batch |
| `GhostRigger.Validation` | `GhostRigger.Domain.Core.Validation` | Domain | Core | Validation | `native\GhostRigger.Domain.Core.Validation\GhostRigger.Domain.Core.Validation.vcxproj` | renamed in Domain batch |
| `GhostRigger.Walkmesh` | `GhostRigger.Domain.Core.Walkmesh` | Domain | Core | Walkmesh | `native\GhostRigger.Domain.Core.Walkmesh\GhostRigger.Domain.Core.Walkmesh.vcxproj` | renamed in Domain batch |
| `GhostRigger.Workbench` | `GhostRigger.Domain.Core.Workbench` | Domain | Core | Workbench | `native\GhostRigger.Domain.Core.Workbench\GhostRigger.Domain.Core.Workbench.vcxproj` | renamed in Domain batch |
| `GhostRigger.Workflow` | `GhostRigger.Domain.Core.Workflow` | Domain | Core | Workflow | `native\GhostRigger.Domain.Core.Workflow\GhostRigger.Domain.Core.Workflow.vcxproj` | renamed in Domain batch |
| `GhostRigger.GUI.Camera` | `GhostRigger.GUI.Boundary.Camera` | GUI | Boundary | Camera | `native\GhostRigger.GUI.Boundary.Camera\GhostRigger.GUI.Boundary.Camera.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Dialogs` | `GhostRigger.GUI.Boundary.Dialogs` | GUI | Boundary | Dialogs | `native\GhostRigger.GUI.Boundary.Dialogs\GhostRigger.GUI.Boundary.Dialogs.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Gizmo` | `GhostRigger.GUI.Boundary.Gizmo` | GUI | Boundary | Gizmo | `native\GhostRigger.GUI.Boundary.Gizmo\GhostRigger.GUI.Boundary.Gizmo.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Integration` | `GhostRigger.GUI.Boundary.Integration` | GUI | Boundary | Integration | `native\GhostRigger.GUI.Boundary.Integration\GhostRigger.GUI.Boundary.Integration.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Lighting` | `GhostRigger.GUI.Boundary.Lighting` | GUI | Boundary | Lighting | `native\GhostRigger.GUI.Boundary.Lighting\GhostRigger.GUI.Boundary.Lighting.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Panels` | `GhostRigger.GUI.Boundary.Panels` | GUI | Boundary | Panels | `native\GhostRigger.GUI.Boundary.Panels\GhostRigger.GUI.Boundary.Panels.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Rendering` | `GhostRigger.GUI.Boundary.Rendering` | GUI | Boundary | Rendering | `native\GhostRigger.GUI.Boundary.Rendering\GhostRigger.GUI.Boundary.Rendering.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.SequenceEditor` | `GhostRigger.GUI.Boundary.SequenceEditor` | GUI | Boundary | SequenceEditor | `native\GhostRigger.GUI.Boundary.SequenceEditor\GhostRigger.GUI.Boundary.SequenceEditor.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Textures` | `GhostRigger.GUI.Boundary.Textures` | GUI | Boundary | Textures | `native\GhostRigger.GUI.Boundary.Textures\GhostRigger.GUI.Boundary.Textures.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Theme` | `GhostRigger.GUI.Boundary.Theme` | GUI | Boundary | Theme | `native\GhostRigger.GUI.Boundary.Theme\GhostRigger.GUI.Boundary.Theme.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Viewports` | `GhostRigger.GUI.Boundary.Viewports` | GUI | Boundary | Viewports | `native\GhostRigger.GUI.Boundary.Viewports\GhostRigger.GUI.Boundary.Viewports.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.Adapters.Files` | `GhostRigger.Adapters.IO.Files` | Adapters | IO | Files | `native\GhostRigger.Adapters.IO.Files\GhostRigger.Adapters.IO.Files.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.GPU` | `GhostRigger.Adapters.Hardware.GPU` | Adapters | Hardware | GPU | `native\GhostRigger.Adapters.Hardware.GPU\GhostRigger.Adapters.Hardware.GPU.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtAutorig` | `GhostRigger.Adapters.Qt.Autorig` | Adapters | Qt | Autorig | `native\GhostRigger.Adapters.Qt.Autorig\GhostRigger.Adapters.Qt.Autorig.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtIPC` | `GhostRigger.Adapters.Qt.IPC` | Adapters | Qt | IPC | `native\GhostRigger.Adapters.Qt.IPC\GhostRigger.Adapters.Qt.IPC.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtViewport` | `GhostRigger.Adapters.Qt.Viewport` | Adapters | Qt | Viewport | `native\GhostRigger.Adapters.Qt.Viewport\GhostRigger.Adapters.Qt.Viewport.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.Rendering` | `GhostRigger.Adapters.Rendering.Core` | Adapters | Rendering | Core | `native\GhostRigger.Adapters.Rendering.Core\GhostRigger.Adapters.Rendering.Core.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.Scripts` | `GhostRigger.Adapters.Scripting.Core` | Adapters | Scripting | Core | `native\GhostRigger.Adapters.Scripting.Core\GhostRigger.Adapters.Scripting.Core.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Systems.BAS` | `GhostRigger.Systems.Feature.BAS` | Systems | Feature | BAS | `native\GhostRigger.Systems.Feature.BAS\GhostRigger.Systems.Feature.BAS.vcxproj` | renamed in Systems batch |
