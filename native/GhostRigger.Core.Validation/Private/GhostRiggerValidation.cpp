#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerValidation.h"
#include "ValidationBus.h"

namespace validation_bus = ghostrigger::core::validation::core::validation::validation_bus;

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"validation_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Validation",)"
    R"("source_package":"src/core/validation",)"
    R"("owner_surface":"Validation services",)"
    R"("owner_package":"native/GhostRigger.Core.Validation",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","validation_bus_severity_contracts","validation_bus_subsystem_contracts"],)"
    R"("python_owns":["validation_bus_publish_subscribe_lifecycle","validation_report_object_graph","validation_issue_sha1_ids","workflow_policy","ui_state"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"validation_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Validation",)"
    R"("source_package":"src/core/validation",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_validation_bus_scope":"severity_subsystem_contracts"})";

} // namespace

extern "C" {

GHOSTRIGGER_VALIDATION_API const char* gr_validation_version() {
    return kVersion;
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Validation","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/validation",)"
           R"("owner_surface":"Validation services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","validation_bus_severity_rank","validation_bus_severity_values","validation_bus_subsystem_values"],)"
           R"("native_scope":"validation_bus severity/subsystem contracts",)"
           R"("python_fallback_reason":"full report bus lifecycle still uses Python callbacks, dataclasses, SHA1 issue ids, and ResourceAddress object serialization",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_VALIDATION_API int gr_validation_severity_rank(const char* severity) {
    return validation_bus::severity_rank(severity == nullptr ? "" : severity);
}

GHOSTRIGGER_VALIDATION_API int gr_validation_is_valid_severity(const char* severity) {
    return validation_bus::is_valid_severity(severity == nullptr ? "" : severity) ? 1 : 0;
}

GHOSTRIGGER_VALIDATION_API int gr_validation_is_valid_subsystem(const char* subsystem) {
    return validation_bus::is_valid_subsystem(subsystem == nullptr ? "" : subsystem) ? 1 : 0;
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_severity_values_json() {
    return validation_bus::severity_values_json();
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_subsystem_values_json() {
    return validation_bus::subsystem_values_json();
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_validation_bus_schema_json() {
    return validation_bus::validation_bus_schema_json();
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
