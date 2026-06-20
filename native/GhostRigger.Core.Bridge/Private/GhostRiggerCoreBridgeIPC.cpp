#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerCoreBridgeIPC.h"

#include <windows.h>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"core_bridge_ipc_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Bridge",)"
    R"("source_package":"src/adapters/qt_ipc;src/adapters/rendering;src/adapters/unreal",)"
    R"("owner_surface":"Qt IPC adapters",)"
    R"("owner_package":"native/GhostRigger.Core.Bridge",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"core_bridge_ipc_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Bridge",)"
    R"("source_package":"src/adapters/qt_ipc;src/adapters/rendering;src/adapters/unreal",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true})";

using qt_ipc_callback = void (*)(void*);

bool qt_ipc_runtime_available() {
    return GetModuleHandleW(L"Qt6Core.dll") != nullptr || GetModuleHandleW(L"Qt5Core.dll") != nullptr;
}

struct qt_ipc_callback_task {
    qt_ipc_callback callback;
    void* user_data;
};

DWORD CALLBACK qt_ipc_execute_callback(PVOID parameter) {
    qt_ipc_callback_task* task = static_cast<qt_ipc_callback_task*>(parameter);
    if (task == nullptr) {
        return 0;
    }
    if (task->callback != nullptr) {
        task->callback(task->user_data);
    }
    delete task;
    return 0;
}

bool qt_ipc_marshal_to_gui_thread(qt_ipc_callback callback, void* user_data) {
    if (callback == nullptr || !qt_ipc_runtime_available()) {
        return false;
    }

    auto* task = new qt_ipc_callback_task{callback, user_data};
    if (QueueUserWorkItem(qt_ipc_execute_callback, task, WT_EXECUTEDEFAULT) != FALSE) {
        return true;
    }

    delete task;
    return false;
}

} // namespace

extern "C" {

GHOSTRIGGER_CORE_BRIDGE_IPC_API const char* gr_core_bridge_ipc_version() {
    return kVersion;
}

GHOSTRIGGER_CORE_BRIDGE_IPC_API const char* gr_core_bridge_ipc_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Bridge","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/adapters/qt_ipc;src/adapters/rendering;src/adapters/unreal",)"
           R"("owner_surface":"Qt IPC adapters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","marshal_to_gui_thread"],)"
           R"("python_fallback_required":false})";
}

GHOSTRIGGER_CORE_BRIDGE_IPC_API const char* gr_core_bridge_ipc_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_CORE_BRIDGE_IPC_API const char* gr_core_bridge_ipc_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_CORE_BRIDGE_IPC_API int gr_core_bridge_ipc_marshal_to_gui_thread(qt_ipc_callback callback, void* user_data) {
    return qt_ipc_marshal_to_gui_thread(callback, user_data) ? 1 : 0;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native::core::payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native::core::payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
