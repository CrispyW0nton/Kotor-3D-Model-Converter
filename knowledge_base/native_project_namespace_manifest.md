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
| `GhostRigger.Skeleton` | `GhostRigger.Core.Skeleton` | Headless skeleton domain package owning skeleton builder/data contracts. |
| `GhostRigger.Sequence` | `GhostRigger.Core.Tools.SequenceEditor` | Merged into the canonical native SequenceEditor tool surface. |
| `GhostRigger.Tools.NodesSkeletonBrowser` | `GhostRigger.Core.Tools.NodeSkeletonBrowser` | Actual solution spelling uses `NodesSkeletonBrowser`; canonical workflow name should use the requested singular `NodeSkeletonBrowser`. |

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
| `GhostRigger.Graphics.Renderer.Contracts` | `GhostRigger.Graphics.Renderer.Shared.Contracts` | Renderer | Shared | Contracts | `native\GhostRigger.Graphics.Renderer.Shared.Contracts\GhostRigger.Graphics.Renderer.Shared.Contracts.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Graphics.Renderer.D3D12` | `GhostRigger.Graphics.Renderer.Backend.D3D12` | Renderer | Backend | D3D12 | `native\GhostRigger.Graphics.Renderer.Backend.D3D12\GhostRigger.Graphics.Renderer.Backend.D3D12.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Graphics.Renderer.ModernGL` | `GhostRigger.Graphics.Renderer.Backend.ModernGL` | Renderer | Backend | ModernGL | `native\GhostRigger.Graphics.Renderer.Backend.ModernGL\GhostRigger.Graphics.Renderer.Backend.ModernGL.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Graphics.Renderer.Null` | `GhostRigger.Graphics.Renderer.Backend.Null` | Renderer | Backend | Null | `native\GhostRigger.Graphics.Renderer.Backend.Null\GhostRigger.Graphics.Renderer.Backend.Null.vcxproj` | renamed in Renderer batch |
| `GhostRigger.Graphics.Renderer.PyGFX` | `GhostRigger.Graphics.Renderer.Backend.PyGFX` | Renderer | Backend | PyGFX | `native\GhostRigger.Graphics.Renderer.Backend.PyGFX\GhostRigger.Graphics.Renderer.Backend.PyGFX.vcxproj` | renamed in Renderer batch |
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
| `GhostRigger.Windows.AnimationRetargetWorkbench` | `GhostRigger.Windows.Workbench.AnimationRetarget` | Windows | Workbench | AnimationRetarget | `native\GhostRigger.Windows.Workbench.AnimationRetarget\GhostRigger.Windows.Workbench.AnimationRetarget.vcxproj` | renamed in Windows batch |
| `GhostRigger.Windows.LegacyRiggingWindow` | `GhostRigger.Windows.Legacy.Rigging` | Windows | Legacy | Rigging | `native\GhostRigger.Windows.Legacy.Rigging\GhostRigger.Windows.Legacy.Rigging.vcxproj` | renamed in Windows batch |
| `GhostRigger.Windows.LevelEditor` | `GhostRigger.Windows.Editor.Level` | Windows | Editor | Level | `native\GhostRigger.Windows.Editor.Level\GhostRigger.Windows.Editor.Level.vcxproj` | renamed in Windows batch |
| `GhostRigger.Windows.MainWindow` | `GhostRigger.Windows.Shell.Main` | Windows | Shell | Main | `native\GhostRigger.Windows.Shell.Main\GhostRigger.Windows.Shell.Main.vcxproj` | renamed in Windows batch |
| `GhostRigger.Windows.UnrealAnimatorWindow` | `GhostRigger.Windows.Workbench.UnrealAnimator` | Windows | Workbench | UnrealAnimator | `native\GhostRigger.Windows.Workbench.UnrealAnimator\GhostRigger.Windows.Workbench.UnrealAnimator.vcxproj` | renamed in Windows batch |
| `GhostRigger.Animation` | `GhostRigger.Core.Animation` | Domain | Core | Animation | `native\GhostRigger.Core.Animation\GhostRigger.Core.Animation.vcxproj` | renamed in Domain batch |
| `GhostRigger.AnimationRetargeting` | `GhostRigger.Core.AnimationRetargeting` | Domain | Core | AnimationRetargeting | `native\GhostRigger.Core.AnimationRetargeting\GhostRigger.Core.AnimationRetargeting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Assets` | `GhostRigger.Core.Assets` | Domain | Core | Assets | `native\GhostRigger.Core.Assets\GhostRigger.Core.Assets.vcxproj` | renamed in Domain batch |
| `GhostRigger.Autorig` | `GhostRigger.Core.Autorig` | Domain | Core | Autorig | `native\GhostRigger.Core.Autorig\GhostRigger.Core.Autorig.vcxproj` | renamed in Domain batch |
| `GhostRigger.Camera` | `GhostRigger.Core.Camera` | Domain | Core | Camera | `native\GhostRigger.Core.Camera\GhostRigger.Core.Camera.vcxproj` | renamed in Domain batch |
| `GhostRigger.Characters` | `GhostRigger.Core.Characters` | Domain | Core | Characters | `native\GhostRigger.Core.Characters\GhostRigger.Core.Characters.vcxproj` | renamed in Domain batch |
| `GhostRigger.Converters` | `GhostRigger.Core.Converters` | Domain | Core | Converters | `native\GhostRigger.Core.Converters\GhostRigger.Core.Converters.vcxproj` | renamed in Domain batch |
| `GhostRigger.Diagnostics` | `GhostRigger.Core.Diagnostics` | Domain | Core | Diagnostics | `native\GhostRigger.Core.Diagnostics\GhostRigger.Core.Diagnostics.vcxproj` | renamed in Domain batch |
| `GhostRigger.Export` | `GhostRigger.Core.Export` | Domain | Core | Export | `native\GhostRigger.Core.Export\GhostRigger.Core.Export.vcxproj` | renamed in Domain batch |
| `GhostRigger.Formats` | `GhostRigger.Core.Formats` | Domain | Core | Formats | `native\GhostRigger.Core.Formats\GhostRigger.Core.Formats.vcxproj` | renamed in Domain batch |
| `GhostRigger.Game` | `GhostRigger.Core.Game` | Domain | Core | Game | `native\GhostRigger.Core.Game\GhostRigger.Core.Game.vcxproj` | renamed in Domain batch |
| `GhostRigger.GameLibrary` | `GhostRigger.Core.GameLibrary` | Domain | Core | GameLibrary | `native\GhostRigger.Core.GameLibrary\GhostRigger.Core.GameLibrary.vcxproj` | renamed in Domain batch |
| `GhostRigger.Geometry` | `GhostRigger.Core.Geometry` | Domain | Core | Geometry | `native\GhostRigger.Core.Geometry\GhostRigger.Core.Geometry.vcxproj` | renamed in Domain batch |
| `GhostRigger.Gizmo` | `GhostRigger.Core.Gizmo` | Domain | Core | Gizmo | `native\GhostRigger.Core.Gizmo\GhostRigger.Core.Gizmo.vcxproj` | renamed in Domain batch |
| `GhostRigger.Graphics` | `GhostRigger.Core.Graphics` | Domain | Core | Graphics | `native\GhostRigger.Core.Graphics\GhostRigger.Core.Graphics.vcxproj` | renamed in Domain batch |
| `GhostRigger.Infra` | `GhostRigger.Core.Infrastructure` | Domain | Core | Infrastructure | `native\GhostRigger.Core.Infrastructure\GhostRigger.Core.Infrastructure.vcxproj` | renamed in Domain batch |
| `GhostRigger.IO` | `GhostRigger.Core.IO` | Domain | Core | IO | `native\GhostRigger.Core.IO\GhostRigger.Core.IO.vcxproj` | renamed in Domain batch |
| `GhostRigger.IPC` | `GhostRigger.Core.IPC` | Domain | Core | IPC | `native\GhostRigger.Core.IPC\GhostRigger.Core.IPC.vcxproj` | renamed in Domain batch |
| `GhostRigger.KotorMCP` | `GhostRigger.Core.KotorMCP` | Domain | Core | KotorMCP | `native\GhostRigger.Core.KotorMCP\GhostRigger.Core.KotorMCP.vcxproj` | renamed in Domain batch |
| `GhostRigger.Level` | `GhostRigger.Core.Level` | Domain | Core | Level | `native\GhostRigger.Core.Level\GhostRigger.Core.Level.vcxproj` | renamed in Domain batch |
| `GhostRigger.Lighting` | `GhostRigger.Core.Lighting` | Domain | Core | Lighting | `native\GhostRigger.Core.Lighting\GhostRigger.Core.Lighting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Math` | `GhostRigger.Core.Math` | Domain | Core | Math | `native\GhostRigger.Core.Math\GhostRigger.Core.Math.vcxproj` | renamed in Domain batch |
| `GhostRigger.MDL` | `GhostRigger.Core.MDL` | Domain | Core | MDL | `native\GhostRigger.Core.MDL\GhostRigger.Core.MDL.vcxproj` | renamed in Domain batch |
| `GhostRigger.Measurement` | `GhostRigger.Core.Measurement` | Domain | Core | Measurement | `native\GhostRigger.Core.Measurement\GhostRigger.Core.Measurement.vcxproj` | renamed in Domain batch |
| `GhostRigger.MeshTools` | `GhostRigger.Core.MeshTools` | Domain | Core | MeshTools | `native\GhostRigger.Core.MeshTools\GhostRigger.Core.MeshTools.vcxproj` | renamed in Domain batch |
| `GhostRigger.Modules` | `GhostRigger.Core.Modules` | Domain | Core | Modules | `native\GhostRigger.Core.Modules\GhostRigger.Core.Modules.vcxproj` | renamed in Domain batch |
| `GhostRigger.Ports` | `GhostRigger.Core.Ports` | Domain | Core | Ports | `native\GhostRigger.Core.Ports\GhostRigger.Core.Ports.vcxproj` | renamed in Domain batch |
| `GhostRigger.Project` | `GhostRigger.Core.Project` | Domain | Core | Project | `native\GhostRigger.Core.Project\GhostRigger.Core.Project.vcxproj` | renamed in Domain batch |
| `GhostRigger.Rendering` | `GhostRigger.Core.Rendering` | Domain | Core | Rendering | `native\GhostRigger.Core.Rendering\GhostRigger.Core.Rendering.vcxproj` | renamed in Domain batch |
| `GhostRigger.Resources` | `GhostRigger.Core.Resources` | Domain | Core | Resources | `native\GhostRigger.Core.Resources\GhostRigger.Core.Resources.vcxproj` | renamed in Domain batch |
| `GhostRigger.Retargeting` | `GhostRigger.Core.Retargeting` | Domain | Core | Retargeting | `native\GhostRigger.Core.Retargeting\GhostRigger.Core.Retargeting.vcxproj` | renamed in Domain batch |
| `GhostRigger.Scene` | `GhostRigger.Core.Scene` | Domain | Core | Scene | `native\GhostRigger.Core.Scene\GhostRigger.Core.Scene.vcxproj` | renamed in Domain batch |
| `GhostRigger.Sequence` | `GhostRigger.Core.Tools.SequenceEditor` | Domain | Core | Sequence | `native\GhostRigger.Core.Tools.SequenceEditor\GhostRigger.Core.Tools.SequenceEditor.vcxproj` | renamed in Sequence merge; retired from solution |
| `GhostRigger.Skeleton` | `GhostRigger.Core.Skeleton` | Domain | Core | Skeleton | `native\GhostRigger.Core.Skeleton\GhostRigger.Core.Skeleton.vcxproj` | renamed in Domain batch; missing from requested map |
| `GhostRigger.Special` | `GhostRigger.Core.Special` | Domain | Core | Special | `native\GhostRigger.Core.Special\GhostRigger.Core.Special.vcxproj` | renamed in Domain batch |
| `GhostRigger.Templates` | `GhostRigger.Core.Templates` | Domain | Core | Templates | `native\GhostRigger.Core.Templates\GhostRigger.Core.Templates.vcxproj` | renamed in Domain batch |
| `GhostRigger.Unreal` | `GhostRigger.Core.Unreal` | Domain | Core | Unreal | `native\GhostRigger.Core.Unreal\GhostRigger.Core.Unreal.vcxproj` | renamed in Domain batch |
| `GhostRigger.Validation` | `GhostRigger.Core.Validation` | Domain | Core | Validation | `native\GhostRigger.Core.Validation\GhostRigger.Core.Validation.vcxproj` | renamed in Domain batch |
| `GhostRigger.Walkmesh` | `GhostRigger.Core.Walkmesh` | Domain | Core | Walkmesh | `native\GhostRigger.Core.Walkmesh\GhostRigger.Core.Walkmesh.vcxproj` | renamed in Domain batch |
| `GhostRigger.Workbench` | `GhostRigger.Core.Workbench` | Domain | Core | Workbench | `native\GhostRigger.Core.Workbench\GhostRigger.Core.Workbench.vcxproj` | renamed in Domain batch |
| `GhostRigger.Workflow` | `GhostRigger.Core.Workflow` | Domain | Core | Workflow | `native\GhostRigger.Core.Workflow\GhostRigger.Core.Workflow.vcxproj` | renamed in Domain batch |
| `GhostRigger.GUI.Camera` | `GhostRigger.Core.GUI.Camera` | GUI | Boundary | Camera | `native\GhostRigger.Core.GUI.Camera\GhostRigger.Core.GUI.Camera.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Dialogs` | `GhostRigger.Core.GUI.Dialogs` | GUI | Boundary | Dialogs | `native\GhostRigger.Core.GUI.Dialogs\GhostRigger.Core.GUI.Dialogs.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Gizmo` | `GhostRigger.Core.GUI.Gizmo` | GUI | Boundary | Gizmo | `native\GhostRigger.Core.GUI.Gizmo\GhostRigger.Core.GUI.Gizmo.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Integration` | `GhostRigger.Core.GUI.Integration` | GUI | Boundary | Integration | `native\GhostRigger.Core.GUI.Integration\GhostRigger.Core.GUI.Integration.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Lighting` | `GhostRigger.Core.GUI.Lighting` | GUI | Boundary | Lighting | `native\GhostRigger.Core.GUI.Lighting\GhostRigger.Core.GUI.Lighting.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Panels` | `GhostRigger.Core.GUI.Panels` | GUI | Boundary | Panels | `native\GhostRigger.Core.GUI.Panels\GhostRigger.Core.GUI.Panels.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Rendering` | `GhostRigger.Core.GUI.Rendering` | GUI | Boundary | Rendering | `native\GhostRigger.Core.GUI.Rendering\GhostRigger.Core.GUI.Rendering.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.SequenceEditor` | `GhostRigger.Core.GUI.SequenceEditor` | GUI | Boundary | SequenceEditor | `native\GhostRigger.Core.GUI.SequenceEditor\GhostRigger.Core.GUI.SequenceEditor.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Textures` | `GhostRigger.Core.GUI.Textures` | GUI | Boundary | Textures | `native\GhostRigger.Core.GUI.Textures\GhostRigger.Core.GUI.Textures.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Theme` | `GhostRigger.Core.GUI.Theme` | GUI | Boundary | Theme | `native\GhostRigger.Core.GUI.Theme\GhostRigger.Core.GUI.Theme.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.GUI.Viewports` | `GhostRigger.Core.GUI.Viewports` | GUI | Boundary | Viewports | `native\GhostRigger.Core.GUI.Viewports\GhostRigger.Core.GUI.Viewports.vcxproj` | renamed in GUI Boundary batch |
| `GhostRigger.Adapters.Files` | `GhostRigger.Adapters.IO.Files` | Adapters | IO | Files | `native\GhostRigger.Adapters.IO.Files\GhostRigger.Adapters.IO.Files.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.GPU` | `GhostRigger.Adapters.Hardware.GPU` | Adapters | Hardware | GPU | `native\GhostRigger.Adapters.Hardware.GPU\GhostRigger.Adapters.Hardware.GPU.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtAutorig` | `GhostRigger.Adapters.Qt.Autorig` | Adapters | Qt | Autorig | `native\GhostRigger.Adapters.Qt.Autorig\GhostRigger.Adapters.Qt.Autorig.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtIPC` | `GhostRigger.Adapters.Qt.IPC` | Adapters | Qt | IPC | `native\GhostRigger.Adapters.Qt.IPC\GhostRigger.Adapters.Qt.IPC.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.QtViewport` | `GhostRigger.Adapters.Qt.Viewport` | Adapters | Qt | Viewport | `native\GhostRigger.Adapters.Qt.Viewport\GhostRigger.Adapters.Qt.Viewport.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.Rendering` | `GhostRigger.Adapters.Rendering.Core` | Adapters | Rendering | Core | `native\GhostRigger.Adapters.Rendering.Core\GhostRigger.Adapters.Rendering.Core.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Adapters.Scripts` | `GhostRigger.Adapters.Scripting.Core` | Adapters | Scripting | Core | `native\GhostRigger.Adapters.Scripting.Core\GhostRigger.Adapters.Scripting.Core.vcxproj` | renamed in Adapters batch |
| `GhostRigger.Systems.BAS` | `GhostRigger.Core.Tools.BAS` | Systems | Feature | BAS | `native\GhostRigger.Core.Tools.BAS\GhostRigger.Core.Tools.BAS.vcxproj` | renamed in BAS merge; retired from solution |
