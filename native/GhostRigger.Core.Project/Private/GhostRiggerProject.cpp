#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerProject.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"project_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Project.vcxproj",)"
    R"("source_package":"src/core/project",)"
    R"("owner_surface":"Project and session infrastructure",)"
    R"("owner_package":"native/GhostRigger.Core.Project.vcxproj",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","resource_address_contracts"],)"
    R"("python_owns":["project_model_graph_serialization","project_validation_issue_generation","dynamic_resource_address_coercion"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"project_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Project.vcxproj",)"
    R"("source_package":"src/core/project",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_project_scope":"resource_address_contracts"})";

} // namespace

extern "C" {

GHOSTRIGGER_PROJECT_API const char* gr_project_version() {
    return kVersion;
}

GHOSTRIGGER_PROJECT_API const char* gr_project_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Project.vcxproj","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/project",)"
           R"("owner_surface":"Project and session infrastructure","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","resource_address_contracts"],)"
           R"("native_scope":"project ResourceAddress scheme, normalization, stable-key, display-name, and flat JSON contracts",)"
           R"("python_fallback_reason":"dynamic object coercion, arbitrary metadata value preservation, project model graph serialization, and project validation issue generation remain Python-owned until their callers are ported",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_PROJECT_API const char* gr_project_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_PROJECT_API const char* gr_project_dependency_schema_json() {
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
