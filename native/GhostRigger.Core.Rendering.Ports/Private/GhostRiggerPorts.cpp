#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerPorts.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"ports_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Rendering.Ports",)"
    R"("source_package":"src/core/ports",)"
    R"("owner_surface":"Core port contracts",)"
    R"("owner_package":"native/GhostRigger.Core.Rendering.Ports",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"ports_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Rendering.Ports",)"
    R"("source_package":"src/core/ports",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_PORTS_API const char* gr_ports_version() {
    return kVersion;
}

GHOSTRIGGER_PORTS_API const char* gr_ports_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Rendering.Ports","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/ports",)"
           R"("owner_surface":"Core port contracts","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_PORTS_API const char* gr_ports_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_PORTS_API const char* gr_ports_dependency_schema_json() {
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
