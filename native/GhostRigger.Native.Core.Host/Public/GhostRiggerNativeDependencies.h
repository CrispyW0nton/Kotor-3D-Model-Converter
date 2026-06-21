#pragma once

#include <cstddef>

namespace ghostrigger::native::core::host {

struct NativeDependencySpec {
    const wchar_t* name;
    const wchar_t* dll_name;
};

inline constexpr NativeDependencySpec kNativeDependencySpecs[] = {
    {L"GhostRigger.Core.Automation", L"GhostRigger.Core.Automation.dll"},
    {L"GhostRigger.Core.Unreal", L"GhostRigger.Core.Unreal.dll"},
    {L"GhostRigger.Core.GUI.Display", L"GhostRigger.Core.GUI.Display.dll"},
    {L"GhostRigger.Core.GUI.Helpers", L"GhostRigger.Core.GUI.Helpers.dll"},
    {L"GhostRigger.Core.IO", L"GhostRigger.Core.IO.dll"},
    {L"GhostRigger.Core.Math", L"GhostRigger.Core.Math.dll"},
    {L"GhostRigger.Core.Project", L"GhostRigger.Core.Project.dll"},
    {L"GhostRigger.Core.Qt", L"GhostRigger.Core.Qt.dll"},
    {L"GhostRigger.Core.Rendering", L"GhostRigger.Core.Rendering.dll"},
    {L"GhostRigger.Core.Resources", L"GhostRigger.Core.Resources.dll"},
    {L"GhostRigger.Core.Scene", L"GhostRigger.Core.Scene.dll"},
    {L"GhostRigger.Core.Tools", L"GhostRigger.Core.Tools.dll"},
    {L"GhostRigger.Core.Validation", L"GhostRigger.Core.Validation.dll"},
    {L"GhostRigger.Core.Workflow", L"GhostRigger.Core.Workflow.dll"},
    {L"GhostRigger.Native.Core.Foundation", L"GhostRigger.Native.Core.Foundation.dll"},
    {L"GhostRigger.Runtime.Core", L"GhostRigger.Runtime.Core.dll"},
    {L"GhostRigger.Runtime.Core.Host", L"GhostRigger.Runtime.Core.Host.dll"},
    {L"GhostRigger.Runtime.Shared", L"GhostRigger.Runtime.Shared.dll"},
};

inline constexpr std::size_t kNativeDependencySpecCount = sizeof(kNativeDependencySpecs) / sizeof(kNativeDependencySpecs[0]);

} // namespace ghostrigger::native::core::host
