#include "GhostRiggerInfra.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"infra_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Infra",)"
    R"("source_package":"src/infra",)"
    R"("owner_surface":"Infrastructure services",)"
    R"("owner_package":"native/GhostRigger.Infra",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"infra_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Infra",)"
    R"("source_package":"src/infra",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_INFRA_API const char* gr_infra_version() {
    return kVersion;
}

GHOSTRIGGER_INFRA_API const char* gr_infra_capabilities_json() {
    return R"({"name":"GhostRigger.Infra","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/infra",)"
           R"("owner_surface":"Infrastructure services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_INFRA_API const char* gr_infra_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_INFRA_API const char* gr_infra_dependency_schema_json() {
    return kDependencySchema;
}

}