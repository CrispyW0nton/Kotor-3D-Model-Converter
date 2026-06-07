#include "GhostRiggerWalkmesh.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"walkmesh_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Walkmesh",)"
    R"("source_package":"src/core/walkmesh",)"
    R"("owner_surface":"Walkmesh editing",)"
    R"("owner_package":"native/GhostRigger.Walkmesh",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"walkmesh_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Walkmesh",)"
    R"("source_package":"src/core/walkmesh",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_version() {
    return kVersion;
}

GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_capabilities_json() {
    return R"({"name":"GhostRigger.Walkmesh","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/walkmesh",)"
           R"("owner_surface":"Walkmesh editing","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_dependency_schema_json() {
    return kDependencySchema;
}

}