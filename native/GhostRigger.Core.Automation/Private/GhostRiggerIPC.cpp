#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerIPC.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"ipc_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Automation",)"
    R"("source_package":"src/ipc;src/kotormcp;src/adapters/scripts",)"
    R"("owner_surface":"IPC services",)"
    R"("owner_package":"native/GhostRigger.Core.Automation",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"ipc_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Automation",)"
    R"("source_package":"src/ipc;src/kotormcp;src/adapters/scripts",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true})";

} // namespace

extern "C" {

GHOSTRIGGER_IPC_API const char* gr_ipc_version() {
    return kVersion;
}

GHOSTRIGGER_IPC_API const char* gr_ipc_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Automation","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/ipc;src/kotormcp;src/adapters/scripts",)"
           R"("owner_surface":"IPC services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("ipc_contracts_native":true,)"
           R"("native_tool_command_routes":true,)"
           R"("ipc_runtime_python_fallback":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","program_ports","endpoint_url","request_envelope","response_status","ping_status_message","supports_action","tool_command_routes"],)"
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
    return ghostrigger::native::core::payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native::core::payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
