#include "../GhostRigger.Native.NativeCore/GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerIPC.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"ipc_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.IPC",)"
    R"("source_package":"src/ipc",)"
    R"("owner_surface":"IPC services",)"
    R"("owner_package":"native/GhostRigger.IPC",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"ipc_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.IPC",)"
    R"("source_package":"src/ipc",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_IPC_API const char* gr_ipc_version() {
    return kVersion;
}

GHOSTRIGGER_IPC_API const char* gr_ipc_capabilities_json() {
    return R"({"name":"GhostRigger.IPC","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/ipc",)"
           R"("owner_surface":"IPC services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_IPC_API const char* gr_ipc_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_IPC_API const char* gr_ipc_dependency_schema_json() {
    return kDependencySchema;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native_payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native_payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
