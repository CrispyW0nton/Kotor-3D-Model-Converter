#include "GhostRiggerResources.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"resources_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Resources",)"
    R"("source_package":"src/core/resources",)"
    R"("owner_surface":"Game resource provider core",)"
    R"("owner_package":"native/GhostRigger.Resources",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"resources_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Resources",)"
    R"("source_package":"src/core/resources",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_RESOURCES_API const char* gr_resources_version() {
    return kVersion;
}

GHOSTRIGGER_RESOURCES_API const char* gr_resources_capabilities_json() {
    return R"({"name":"GhostRigger.Resources","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/resources",)"
           R"("owner_surface":"Game resource provider core","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_RESOURCES_API const char* gr_resources_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_RESOURCES_API const char* gr_resources_dependency_schema_json() {
    return kDependencySchema;
}

}