#include "GhostRiggerPythonPayloadResource.h"
#include "Workflow_Animation/GhostRiggerAnimation.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"animation_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Workflow",)"
    R"("source_package":"src/core/animation",)"
    R"("owner_surface":"Animation runtime",)"
    R"("owner_package":"native/GhostRigger.Core.Workflow",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"animation_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Workflow",)"
    R"("source_package":"src/core/animation",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_ANIMATION_API const char* gr_animation_version() {
    return kVersion;
}

GHOSTRIGGER_ANIMATION_API const char* gr_animation_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Workflow","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/animation",)"
           R"("owner_surface":"Animation runtime","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_ANIMATION_API const char* gr_animation_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_ANIMATION_API const char* gr_animation_dependency_schema_json() {
    return kDependencySchema;
}

}

