# GhostRigger Native Project Namespace Manifest

Owner: LordVaderCW
Date: 2026-06-14
Scope: Phase 1 audit for canonical `GhostRigger.Group.Type.ModuleName` project naming.

## Audit Summary

- Real C++ projects in `GhostRigger.sln`: 94
- Solution-folder projects in `GhostRigger.sln`: 0
- Expected real project count: 94
- Rename status: audit only; no canonical project renames have been applied.
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
| `GhostRigger.Native` | `GhostRigger.Native.Core.Host` | Native | Core | Host | `native\GhostRigger.Native\GhostRigger.Native.vcxproj` | rename required; missing from requested map |
| `GhostRigger.Native.NativeCore` | `GhostRigger.Native.Core.Foundation` | Native | Core | Foundation | `native\GhostRigger.Native.NativeCore\GhostRigger.Native.NativeCore.vcxproj` | rename required |
| `GhostRigger.Native.NativeCore.Diagnostics` | `GhostRigger.Native.Core.Diagnostics` | Native | Core | Diagnostics | `native\GhostRigger.Native.NativeCore.Diagnostics\GhostRigger.Native.NativeCore.Diagnostics.vcxproj` | rename required |
| `GhostRigger.Native.NativeCore.Math` | `GhostRigger.Native.Core.Math` | Native | Core | Math | `native\GhostRigger.Native.NativeCore.Math\GhostRigger.Native.NativeCore.Math.vcxproj` | rename required |
| `GhostRigger.Runtime` | `GhostRigger.Runtime.Core.Host` | Runtime | Core | Host | `native\GhostRigger.Runtime\GhostRigger.Runtime.vcxproj` | rename required |
| `GhostRigger.Runtime.Shared.Contracts` | `GhostRigger.Runtime.Shared.Contracts` | Runtime | Shared | Contracts | `native\GhostRigger.Runtime.Shared.Contracts\GhostRigger.Runtime.Shared.Contracts.vcxproj` | already canonical |
| `GhostRigger.Runtime.Shared.Descriptors` | `GhostRigger.Runtime.Shared.Descriptors` | Runtime | Shared | Descriptors | `native\GhostRigger.Runtime.Shared.Descriptors\GhostRigger.Runtime.Shared.Descriptors.vcxproj` | already canonical |
| `GhostRigger.Runtime.Shared.Resources` | `GhostRigger.Runtime.Shared.Resources` | Runtime | Shared | Resources | `native\GhostRigger.Runtime.Shared.Resources\GhostRigger.Runtime.Shared.Resources.vcxproj` | already canonical |
| `GhostRigger.Renderer.Contracts` | `GhostRigger.Renderer.Shared.Contracts` | Renderer | Shared | Contracts | `native\GhostRigger.Renderer.Contracts\GhostRigger.Renderer.Contracts.vcxproj` | rename required |
| `GhostRigger.Renderer.D3D12` | `GhostRigger.Renderer.Backend.D3D12` | Renderer | Backend | D3D12 | `native\GhostRigger.Renderer.D3D12\GhostRigger.Renderer.D3D12.vcxproj` | rename required |
| `GhostRigger.Renderer.ModernGL` | `GhostRigger.Renderer.Backend.ModernGL` | Renderer | Backend | ModernGL | `native\GhostRigger.Renderer.ModernGL\GhostRigger.Renderer.ModernGL.vcxproj` | rename required |
| `GhostRigger.Renderer.Null` | `GhostRigger.Renderer.Backend.Null` | Renderer | Backend | Null | `native\GhostRigger.Renderer.Null\GhostRigger.Renderer.Null.vcxproj` | rename required |
| `GhostRigger.Renderer.PyGFX` | `GhostRigger.Renderer.Backend.PyGFX` | Renderer | Backend | PyGFX | `native\GhostRigger.Renderer.PyGFX\GhostRigger.Renderer.PyGFX.vcxproj` | rename required |
| `GhostRigger.Tools.BodyAttachmentSystem` | `GhostRigger.Tools.Workflow.BodyAttachmentSystem` | Tools | Workflow | BodyAttachmentSystem | `native\GhostRigger.Tools.BodyAttachmentSystem\GhostRigger.Tools.BodyAttachmentSystem.vcxproj` | rename required |
| `GhostRigger.Tools.Camera` | `GhostRigger.Tools.Workflow.Camera` | Tools | Workflow | Camera | `native\GhostRigger.Tools.Camera\GhostRigger.Tools.Camera.vcxproj` | rename required |
| `GhostRigger.Tools.CharacterBuilder` | `GhostRigger.Tools.Workflow.CharacterBuilder` | Tools | Workflow | CharacterBuilder | `native\GhostRigger.Tools.CharacterBuilder\GhostRigger.Tools.CharacterBuilder.vcxproj` | rename required |
| `GhostRigger.Tools.ContentBrowser` | `GhostRigger.Tools.Workflow.ContentBrowser` | Tools | Workflow | ContentBrowser | `native\GhostRigger.Tools.ContentBrowser\GhostRigger.Tools.ContentBrowser.vcxproj` | rename required |
| `GhostRigger.Tools.Export` | `GhostRigger.Tools.Workflow.Export` | Tools | Workflow | Export | `native\GhostRigger.Tools.Export\GhostRigger.Tools.Export.vcxproj` | rename required |
| `GhostRigger.Tools.Lighting` | `GhostRigger.Tools.Workflow.Lighting` | Tools | Workflow | Lighting | `native\GhostRigger.Tools.Lighting\GhostRigger.Tools.Lighting.vcxproj` | rename required |
| `GhostRigger.Tools.ModuleMeshes` | `GhostRigger.Tools.Workflow.ModuleMeshes` | Tools | Workflow | ModuleMeshes | `native\GhostRigger.Tools.ModuleMeshes\GhostRigger.Tools.ModuleMeshes.vcxproj` | rename required |
| `GhostRigger.Tools.NodesSkeletonBrowser` | `GhostRigger.Tools.Workflow.NodeSkeletonBrowser` | Tools | Workflow | NodeSkeletonBrowser | `native\GhostRigger.Tools.NodesSkeletonBrowser\GhostRigger.Tools.NodesSkeletonBrowser.vcxproj` | rename required; spelling mismatch in requested map |
| `GhostRigger.Tools.PivotControls` | `GhostRigger.Tools.Workflow.PivotControls` | Tools | Workflow | PivotControls | `native\GhostRigger.Tools.PivotControls\GhostRigger.Tools.PivotControls.vcxproj` | rename required |
| `GhostRigger.Tools.Properties` | `GhostRigger.Tools.Workflow.Properties` | Tools | Workflow | Properties | `native\GhostRigger.Tools.Properties\GhostRigger.Tools.Properties.vcxproj` | rename required |
| `GhostRigger.Tools.ResourceBrowser` | `GhostRigger.Tools.Workflow.ResourceBrowser` | Tools | Workflow | ResourceBrowser | `native\GhostRigger.Tools.ResourceBrowser\GhostRigger.Tools.ResourceBrowser.vcxproj` | rename required |
| `GhostRigger.Tools.Retargeting` | `GhostRigger.Tools.Workflow.Retargeting` | Tools | Workflow | Retargeting | `native\GhostRigger.Tools.Retargeting\GhostRigger.Tools.Retargeting.vcxproj` | rename required |
| `GhostRigger.Tools.SceneInformation` | `GhostRigger.Tools.Workflow.SceneInformation` | Tools | Workflow | SceneInformation | `native\GhostRigger.Tools.SceneInformation\GhostRigger.Tools.SceneInformation.vcxproj` | rename required |
| `GhostRigger.Tools.SequenceEditor` | `GhostRigger.Tools.Workflow.SequenceEditor` | Tools | Workflow | SequenceEditor | `native\GhostRigger.Tools.SequenceEditor\GhostRigger.Tools.SequenceEditor.vcxproj` | rename required |
| `GhostRigger.Tools.SpriteMaterials` | `GhostRigger.Tools.Workflow.SpriteMaterials` | Tools | Workflow | SpriteMaterials | `native\GhostRigger.Tools.SpriteMaterials\GhostRigger.Tools.SpriteMaterials.vcxproj` | rename required |
| `GhostRigger.Tools.TwoDABrowser` | `GhostRigger.Tools.Workflow.TwoDABrowser` | Tools | Workflow | TwoDABrowser | `native\GhostRigger.Tools.TwoDABrowser\GhostRigger.Tools.TwoDABrowser.vcxproj` | rename required |
| `GhostRigger.Windows.AnimationRetargetWorkbench` | `GhostRigger.Windows.Workbench.AnimationRetarget` | Windows | Workbench | AnimationRetarget | `native\GhostRigger.Windows.AnimationRetargetWorkbench\GhostRigger.Windows.AnimationRetargetWorkbench.vcxproj` | rename required |
| `GhostRigger.Windows.LegacyRiggingWindow` | `GhostRigger.Windows.Legacy.Rigging` | Windows | Legacy | Rigging | `native\GhostRigger.Windows.LegacyRiggingWindow\GhostRigger.Windows.LegacyRiggingWindow.vcxproj` | rename required |
| `GhostRigger.Windows.LevelEditor` | `GhostRigger.Windows.Editor.Level` | Windows | Editor | Level | `native\GhostRigger.Windows.LevelEditor\GhostRigger.Windows.LevelEditor.vcxproj` | rename required |
| `GhostRigger.Windows.MainWindow` | `GhostRigger.Windows.Shell.Main` | Windows | Shell | Main | `native\GhostRigger.Windows.MainWindow\GhostRigger.Windows.MainWindow.vcxproj` | rename required |
| `GhostRigger.Windows.UnrealAnimatorWindow` | `GhostRigger.Windows.Workbench.UnrealAnimator` | Windows | Workbench | UnrealAnimator | `native\GhostRigger.Windows.UnrealAnimatorWindow\GhostRigger.Windows.UnrealAnimatorWindow.vcxproj` | rename required |
| `GhostRigger.Animation` | `GhostRigger.Domain.Core.Animation` | Domain | Core | Animation | `native\GhostRigger.Animation\GhostRigger.Animation.vcxproj` | rename required |
| `GhostRigger.AnimationRetargeting` | `GhostRigger.Domain.Core.AnimationRetargeting` | Domain | Core | AnimationRetargeting | `native\GhostRigger.AnimationRetargeting\GhostRigger.AnimationRetargeting.vcxproj` | rename required |
| `GhostRigger.Assets` | `GhostRigger.Domain.Core.Assets` | Domain | Core | Assets | `native\GhostRigger.Assets\GhostRigger.Assets.vcxproj` | rename required |
| `GhostRigger.Autorig` | `GhostRigger.Domain.Core.Autorig` | Domain | Core | Autorig | `native\GhostRigger.Autorig\GhostRigger.Autorig.vcxproj` | rename required |
| `GhostRigger.Camera` | `GhostRigger.Domain.Core.Camera` | Domain | Core | Camera | `native\GhostRigger.Camera\GhostRigger.Camera.vcxproj` | rename required |
| `GhostRigger.Characters` | `GhostRigger.Domain.Core.Characters` | Domain | Core | Characters | `native\GhostRigger.Characters\GhostRigger.Characters.vcxproj` | rename required |
| `GhostRigger.Converters` | `GhostRigger.Domain.Core.Converters` | Domain | Core | Converters | `native\GhostRigger.Converters\GhostRigger.Converters.vcxproj` | rename required |
| `GhostRigger.Diagnostics` | `GhostRigger.Domain.Core.Diagnostics` | Domain | Core | Diagnostics | `native\GhostRigger.Diagnostics\GhostRigger.Diagnostics.vcxproj` | rename required |
| `GhostRigger.Export` | `GhostRigger.Domain.Core.Export` | Domain | Core | Export | `native\GhostRigger.Export\GhostRigger.Export.vcxproj` | rename required |
| `GhostRigger.Formats` | `GhostRigger.Domain.Core.Formats` | Domain | Core | Formats | `native\GhostRigger.Formats\GhostRigger.Formats.vcxproj` | rename required |
| `GhostRigger.Game` | `GhostRigger.Domain.Core.Game` | Domain | Core | Game | `native\GhostRigger.Game\GhostRigger.Game.vcxproj` | rename required |
| `GhostRigger.GameLibrary` | `GhostRigger.Domain.Core.GameLibrary` | Domain | Core | GameLibrary | `native\GhostRigger.GameLibrary\GhostRigger.GameLibrary.vcxproj` | rename required |
| `GhostRigger.Geometry` | `GhostRigger.Domain.Core.Geometry` | Domain | Core | Geometry | `native\GhostRigger.Geometry\GhostRigger.Geometry.vcxproj` | rename required |
| `GhostRigger.Gizmo` | `GhostRigger.Domain.Core.Gizmo` | Domain | Core | Gizmo | `native\GhostRigger.Gizmo\GhostRigger.Gizmo.vcxproj` | rename required |
| `GhostRigger.Graphics` | `GhostRigger.Domain.Core.Graphics` | Domain | Core | Graphics | `native\GhostRigger.Graphics\GhostRigger.Graphics.vcxproj` | rename required |
| `GhostRigger.Infra` | `GhostRigger.Domain.Core.Infrastructure` | Domain | Core | Infrastructure | `native\GhostRigger.Infra\GhostRigger.Infra.vcxproj` | rename required |
| `GhostRigger.IO` | `GhostRigger.Domain.Core.IO` | Domain | Core | IO | `native\GhostRigger.IO\GhostRigger.IO.vcxproj` | rename required |
| `GhostRigger.IPC` | `GhostRigger.Domain.Core.IPC` | Domain | Core | IPC | `native\GhostRigger.IPC\GhostRigger.IPC.vcxproj` | rename required |
| `GhostRigger.KotorMCP` | `GhostRigger.Domain.Core.KotorMCP` | Domain | Core | KotorMCP | `native\GhostRigger.KotorMCP\GhostRigger.KotorMCP.vcxproj` | rename required |
| `GhostRigger.Level` | `GhostRigger.Domain.Core.Level` | Domain | Core | Level | `native\GhostRigger.Level\GhostRigger.Level.vcxproj` | rename required |
| `GhostRigger.Lighting` | `GhostRigger.Domain.Core.Lighting` | Domain | Core | Lighting | `native\GhostRigger.Lighting\GhostRigger.Lighting.vcxproj` | rename required |
| `GhostRigger.Math` | `GhostRigger.Domain.Core.Math` | Domain | Core | Math | `native\GhostRigger.Math\GhostRigger.Math.vcxproj` | rename required |
| `GhostRigger.MDL` | `GhostRigger.Domain.Core.MDL` | Domain | Core | MDL | `native\GhostRigger.MDL\GhostRigger.MDL.vcxproj` | rename required |
| `GhostRigger.Measurement` | `GhostRigger.Domain.Core.Measurement` | Domain | Core | Measurement | `native\GhostRigger.Measurement\GhostRigger.Measurement.vcxproj` | rename required |
| `GhostRigger.MeshTools` | `GhostRigger.Domain.Core.MeshTools` | Domain | Core | MeshTools | `native\GhostRigger.MeshTools\GhostRigger.MeshTools.vcxproj` | rename required |
| `GhostRigger.Modules` | `GhostRigger.Domain.Core.Modules` | Domain | Core | Modules | `native\GhostRigger.Modules\GhostRigger.Modules.vcxproj` | rename required |
| `GhostRigger.Ports` | `GhostRigger.Domain.Core.Ports` | Domain | Core | Ports | `native\GhostRigger.Ports\GhostRigger.Ports.vcxproj` | rename required |
| `GhostRigger.Project` | `GhostRigger.Domain.Core.Project` | Domain | Core | Project | `native\GhostRigger.Project\GhostRigger.Project.vcxproj` | rename required |
| `GhostRigger.Rendering` | `GhostRigger.Domain.Core.Rendering` | Domain | Core | Rendering | `native\GhostRigger.Rendering\GhostRigger.Rendering.vcxproj` | rename required |
| `GhostRigger.Resources` | `GhostRigger.Domain.Core.Resources` | Domain | Core | Resources | `native\GhostRigger.Resources\GhostRigger.Resources.vcxproj` | rename required |
| `GhostRigger.Retargeting` | `GhostRigger.Domain.Core.Retargeting` | Domain | Core | Retargeting | `native\GhostRigger.Retargeting\GhostRigger.Retargeting.vcxproj` | rename required |
| `GhostRigger.Scene` | `GhostRigger.Domain.Core.Scene` | Domain | Core | Scene | `native\GhostRigger.Scene\GhostRigger.Scene.vcxproj` | rename required |
| `GhostRigger.Sequence` | `GhostRigger.Domain.Core.Sequence` | Domain | Core | Sequence | `native\GhostRigger.Sequence\GhostRigger.Sequence.vcxproj` | rename required; missing from requested map |
| `GhostRigger.Skeleton` | `GhostRigger.Domain.Core.Skeleton` | Domain | Core | Skeleton | `native\GhostRigger.Skeleton\GhostRigger.Skeleton.vcxproj` | rename required; missing from requested map |
| `GhostRigger.Special` | `GhostRigger.Domain.Core.Special` | Domain | Core | Special | `native\GhostRigger.Special\GhostRigger.Special.vcxproj` | rename required |
| `GhostRigger.Templates` | `GhostRigger.Domain.Core.Templates` | Domain | Core | Templates | `native\GhostRigger.Templates\GhostRigger.Templates.vcxproj` | rename required |
| `GhostRigger.Unreal` | `GhostRigger.Domain.Core.Unreal` | Domain | Core | Unreal | `native\GhostRigger.Unreal\GhostRigger.Unreal.vcxproj` | rename required |
| `GhostRigger.Validation` | `GhostRigger.Domain.Core.Validation` | Domain | Core | Validation | `native\GhostRigger.Validation\GhostRigger.Validation.vcxproj` | rename required |
| `GhostRigger.Walkmesh` | `GhostRigger.Domain.Core.Walkmesh` | Domain | Core | Walkmesh | `native\GhostRigger.Walkmesh\GhostRigger.Walkmesh.vcxproj` | rename required |
| `GhostRigger.Workbench` | `GhostRigger.Domain.Core.Workbench` | Domain | Core | Workbench | `native\GhostRigger.Workbench\GhostRigger.Workbench.vcxproj` | rename required |
| `GhostRigger.Workflow` | `GhostRigger.Domain.Core.Workflow` | Domain | Core | Workflow | `native\GhostRigger.Workflow\GhostRigger.Workflow.vcxproj` | rename required |
| `GhostRigger.GUI.Camera` | `GhostRigger.GUI.Boundary.Camera` | GUI | Boundary | Camera | `native\GhostRigger.GUI.Camera\GhostRigger.GUI.Camera.vcxproj` | rename required |
| `GhostRigger.GUI.Dialogs` | `GhostRigger.GUI.Boundary.Dialogs` | GUI | Boundary | Dialogs | `native\GhostRigger.GUI.Dialogs\GhostRigger.GUI.Dialogs.vcxproj` | rename required |
| `GhostRigger.GUI.Gizmo` | `GhostRigger.GUI.Boundary.Gizmo` | GUI | Boundary | Gizmo | `native\GhostRigger.GUI.Gizmo\GhostRigger.GUI.Gizmo.vcxproj` | rename required |
| `GhostRigger.GUI.Integration` | `GhostRigger.GUI.Boundary.Integration` | GUI | Boundary | Integration | `native\GhostRigger.GUI.Integration\GhostRigger.GUI.Integration.vcxproj` | rename required |
| `GhostRigger.GUI.Lighting` | `GhostRigger.GUI.Boundary.Lighting` | GUI | Boundary | Lighting | `native\GhostRigger.GUI.Lighting\GhostRigger.GUI.Lighting.vcxproj` | rename required |
| `GhostRigger.GUI.Panels` | `GhostRigger.GUI.Boundary.Panels` | GUI | Boundary | Panels | `native\GhostRigger.GUI.Panels\GhostRigger.GUI.Panels.vcxproj` | rename required |
| `GhostRigger.GUI.Rendering` | `GhostRigger.GUI.Boundary.Rendering` | GUI | Boundary | Rendering | `native\GhostRigger.GUI.Rendering\GhostRigger.GUI.Rendering.vcxproj` | rename required |
| `GhostRigger.GUI.SequenceEditor` | `GhostRigger.GUI.Boundary.SequenceEditor` | GUI | Boundary | SequenceEditor | `native\GhostRigger.GUI.SequenceEditor\GhostRigger.GUI.SequenceEditor.vcxproj` | rename required |
| `GhostRigger.GUI.Textures` | `GhostRigger.GUI.Boundary.Textures` | GUI | Boundary | Textures | `native\GhostRigger.GUI.Textures\GhostRigger.GUI.Textures.vcxproj` | rename required |
| `GhostRigger.GUI.Theme` | `GhostRigger.GUI.Boundary.Theme` | GUI | Boundary | Theme | `native\GhostRigger.GUI.Theme\GhostRigger.GUI.Theme.vcxproj` | rename required |
| `GhostRigger.GUI.Viewports` | `GhostRigger.GUI.Boundary.Viewports` | GUI | Boundary | Viewports | `native\GhostRigger.GUI.Viewports\GhostRigger.GUI.Viewports.vcxproj` | rename required |
| `GhostRigger.Adapters.Files` | `GhostRigger.Adapters.IO.Files` | Adapters | IO | Files | `native\GhostRigger.Adapters.Files\GhostRigger.Adapters.Files.vcxproj` | rename required |
| `GhostRigger.Adapters.GPU` | `GhostRigger.Adapters.Hardware.GPU` | Adapters | Hardware | GPU | `native\GhostRigger.Adapters.GPU\GhostRigger.Adapters.GPU.vcxproj` | rename required |
| `GhostRigger.Adapters.QtAutorig` | `GhostRigger.Adapters.Qt.Autorig` | Adapters | Qt | Autorig | `native\GhostRigger.Adapters.QtAutorig\GhostRigger.Adapters.QtAutorig.vcxproj` | rename required |
| `GhostRigger.Adapters.QtIPC` | `GhostRigger.Adapters.Qt.IPC` | Adapters | Qt | IPC | `native\GhostRigger.Adapters.QtIPC\GhostRigger.Adapters.QtIPC.vcxproj` | rename required |
| `GhostRigger.Adapters.QtViewport` | `GhostRigger.Adapters.Qt.Viewport` | Adapters | Qt | Viewport | `native\GhostRigger.Adapters.QtViewport\GhostRigger.Adapters.QtViewport.vcxproj` | rename required |
| `GhostRigger.Adapters.Rendering` | `GhostRigger.Adapters.Rendering.Core` | Adapters | Rendering | Core | `native\GhostRigger.Adapters.Rendering\GhostRigger.Adapters.Rendering.vcxproj` | rename required |
| `GhostRigger.Adapters.Scripts` | `GhostRigger.Adapters.Scripting.Core` | Adapters | Scripting | Core | `native\GhostRigger.Adapters.Scripts\GhostRigger.Adapters.Scripts.vcxproj` | rename required |
| `GhostRigger.Systems.BAS` | `GhostRigger.Systems.Feature.BAS` | Systems | Feature | BAS | `native\GhostRigger.Systems.BAS\GhostRigger.Systems.BAS.vcxproj` | rename required |

