#include "GhostRiggerValidation.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"validation_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Validation",)"
    R"("source_package":"src/core/validation",)"
    R"("owner_surface":"Validation services",)"
    R"("owner_package":"native/GhostRigger.Validation",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"validation_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Validation",)"
    R"("source_package":"src/core/validation",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_VALIDATION_API const char* gr_validation_version() {
    return kVersion;
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_capabilities_json() {
    return R"({"name":"GhostRigger.Validation","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/validation",)"
           R"("owner_surface":"Validation services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_VALIDATION_API const char* gr_validation_dependency_schema_json() {
    return kDependencySchema;
}

}