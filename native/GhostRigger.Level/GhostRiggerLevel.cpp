#include "GhostRiggerLevel.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"level_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Level",)"
    R"("source_package":"src/core/level",)"
    R"("owner_surface":"Level Editor / KMAP project services",)"
    R"("owner_package":"native/GhostRigger.Level",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"level_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Level",)"
    R"("source_package":"src/core/level",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_LEVEL_API const char* gr_level_version() {
    return kVersion;
}

GHOSTRIGGER_LEVEL_API const char* gr_level_capabilities_json() {
    return R"({"name":"GhostRigger.Level","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/level",)"
           R"("owner_surface":"Level Editor / KMAP project services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_LEVEL_API const char* gr_level_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_LEVEL_API const char* gr_level_dependency_schema_json() {
    return kDependencySchema;
}

}