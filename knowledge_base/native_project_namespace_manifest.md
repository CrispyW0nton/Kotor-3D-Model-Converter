# GhostRigger Native Project Namespace Manifest

Owner: LordVaderCW
Date: 2026-06-20
Scope: Final collapsed native package layout.

This manifest records the current Visual Studio project boundaries after the
ownership-collapse pass. `knowledge_base/package_ownership_model.md` remains the
authority for deciding where future behavior belongs.

## Summary

- Real C++ projects in `GhostRigger.sln`: 19
- Solution-folder projects in `GhostRigger.sln`: 0
- Python-payload DLL projects in `native/GhostRigger.PythonPayloadManifest.json`: 18
- Packaged Python file references: 1,118
- Payload regeneration refreshed the moved Qt IPC and Unreal package payloads.

## Project Manifest

| ProjectName | Owner | ProjectFile | PythonPayload |
| --- | --- | --- | --- |
| `GhostRigger.Core.Automation` | IPC, MCP, scripting, and command automation | `native\GhostRigger.Core.Automation\GhostRigger.Core.Automation.vcxproj` | Yes |
| `GhostRigger.Core.GUI.Display` | Visible GUI display surfaces | `native\GhostRigger.Core.GUI.Display\GhostRigger.Core.GUI.Display.vcxproj` | Yes |
| `GhostRigger.Core.GUI.Helpers` | Interactive viewport helpers and gizmo surfaces | `native\GhostRigger.Core.GUI.Helpers\GhostRigger.Core.GUI.Helpers.vcxproj` | Yes |
| `GhostRigger.Core.IO` | File IO, file formats, serialization, conversion, MDL, FBX, GFF, LYT, and 2DA | `native\GhostRigger.Core.IO\GhostRigger.Core.IO.vcxproj` | Yes |
| `GhostRigger.Core.Math` | Reusable math, camera math, geometry, pivots, projection, and transforms | `native\GhostRigger.Core.Math\GhostRigger.Core.Math.vcxproj` | Yes |
| `GhostRigger.Core.Project` | Project/session infrastructure | `native\GhostRigger.Core.Project\GhostRigger.Core.Project.vcxproj` | Yes |
| `GhostRigger.Core.Qt` | Qt runtime-facing code that is not bridge ownership | `native\GhostRigger.Core.Qt\GhostRigger.Core.Qt.vcxproj` | Yes |
| `GhostRigger.Core.Rendering` | Renderer contracts, render state, materials, textures, GPU policy, and backends | `native\GhostRigger.Core.Rendering\GhostRigger.Core.Rendering.vcxproj` | Yes |
| `GhostRigger.Core.Resources` | Resource discovery, identity, addressing, lifetime, cache, and game library lookup | `native\GhostRigger.Core.Resources\GhostRigger.Core.Resources.vcxproj` | Yes |
| `GhostRigger.Core.Scene` | Scene objects, transforms, hierarchy, selection, skeleton, modules, level, and walkmesh state | `native\GhostRigger.Core.Scene\GhostRigger.Core.Scene.vcxproj` | Yes |
| `GhostRigger.Core.Tools` | User-facing product tools and workflow surfaces | `native\GhostRigger.Core.Tools\GhostRigger.Core.Tools.vcxproj` | Yes |
| `GhostRigger.Core.Unreal` | Unreal integration, Quinn skeleton mapping, and Unreal retarget helpers | `native\GhostRigger.Core.Unreal\GhostRigger.Core.Unreal.vcxproj` | Yes |
| `GhostRigger.Core.Validation` | Validation gates, checks, and reports | `native\GhostRigger.Core.Validation\GhostRigger.Core.Validation.vcxproj` | Yes |
| `GhostRigger.Core.Workflow` | Reusable multi-step workflow systems | `native\GhostRigger.Core.Workflow\GhostRigger.Core.Workflow.vcxproj` | Yes |
| `GhostRigger.Native.Core.Foundation` | Native foundation, diagnostics, package registry payload, and foundation ABI | `native\GhostRigger.Native.Core.Foundation\GhostRigger.Native.Core.Foundation.vcxproj` | Yes |
| `GhostRigger.Native.Core.Host` | Visual Studio native executable host | `native\GhostRigger.Native.Core.Host\GhostRigger.Native.Core.Host.vcxproj` | No |
| `GhostRigger.Runtime.Core` | Runtime diagnostics and infrastructure services | `native\GhostRigger.Runtime.Core\GhostRigger.Runtime.Core.vcxproj` | Yes |
| `GhostRigger.Runtime.Core.Host` | C ABI runtime host used by Python | `native\GhostRigger.Runtime.Core.Host\GhostRigger.Runtime.Core.Host.vcxproj` | Yes |
| `GhostRigger.Runtime.Shared` | Shared runtime contracts, descriptors, resources, and ports | `native\GhostRigger.Runtime.Shared\GhostRigger.Runtime.Shared.vcxproj` | Yes |

## Merge Policy

Do not recreate split DLLs for submodules unless a real runtime, ABI, dependency,
or deployment boundary makes the split necessary. Add new module folders inside
the owning aggregate project first.
