#include "GhostRiggerPythonPayloadResource.h"
#include "Scene_Modules/GhostRiggerModules.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"modules_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Scene",)"
    R"("source_package":"src/core/modules",)"
    R"("owner_surface":"Module Studio / KMAP module services",)"
    R"("owner_package":"native/GhostRigger.Core.Scene",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"modules_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Scene",)"
    R"("source_package":"src/core/modules",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_MODULES_API const char* gr_modules_version() {
    return kVersion;
}

GHOSTRIGGER_MODULES_API const char* gr_modules_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Scene","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/modules",)"
           R"("owner_surface":"Module Studio / KMAP module services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_MODULES_API const char* gr_modules_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_MODULES_API const char* gr_modules_dependency_schema_json() {
    return kDependencySchema;
}

}

