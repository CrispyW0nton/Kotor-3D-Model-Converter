#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerDiagnostics.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"diagnostics_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Diagnostics",)"
    R"("source_package":"src/core/diagnostics",)"
    R"("owner_surface":"Diagnostic services",)"
    R"("owner_package":"native/GhostRigger.Core.Diagnostics",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","module_reference_normalization","module_reference_field_classification","missing_reference_issue_contracts"],)"
    R"("python_owns":["hydrated_module_traversal","available_resource_indexing","resolver_callbacks","mdl_header_diagnostics","crash_sentinel_file_io","logging_integration","character_scene_validation_service"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"diagnostics_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Diagnostics",)"
    R"("source_package":"src/core/diagnostics",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("python_fallback_reason":"Hydrated module traversal, resolver callbacks, model diagnostics, file IO, logging integration, and character-scene validation depend on runtime Python objects or game/model data that need dedicated validated subsystem ports"})";

} // namespace

extern "C" {

GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_version() {
    return kVersion;
}

GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Diagnostics","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/diagnostics",)"
           R"("owner_surface":"Diagnostic services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("diagnostics_contracts_native":true,"diagnostics_runtime_python_fallback":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","module_reference_normalization","module_reference_field_classification","missing_reference_issue_contracts"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_dependency_schema_json() {
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
