#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerAdaptersScripts.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"adapters_scripts_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Adapters.Scripting.Core",)"
    R"("source_package":"src/adapters/scripts",)"
    R"("owner_surface":"Script adapters",)"
    R"("owner_package":"native/GhostRigger.Adapters.Scripting.Core",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"adapters_scripts_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Adapters.Scripting.Core",)"
    R"("source_package":"src/adapters/scripts",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true})";

} // namespace

extern "C" {

GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_version() {
    return kVersion;
}

GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_capabilities_json() {
    return R"({"name":"GhostRigger.Adapters.Scripting.Core","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/adapters/scripts",)"
           R"("owner_surface":"Script adapters","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("unavailable_compiler_native":true,)"
           R"("script_compiler_runtime_python_fallback":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","unavailable_compiler_result","unavailable_compiler_validation_issue"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_dependency_schema_json() {
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
