#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerAnimationRetargeting.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"animation_retargeting_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.AnimationRetargeting",)"
    R"("source_package":"src/core/animation_retargeting",)"
    R"("owner_surface":"Animation retargeting compatibility",)"
    R"("owner_package":"native/GhostRigger.AnimationRetargeting",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"animation_retargeting_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.AnimationRetargeting",)"
    R"("source_package":"src/core/animation_retargeting",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_version() {
    return kVersion;
}

GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_capabilities_json() {
    return R"({"name":"GhostRigger.AnimationRetargeting","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/animation_retargeting",)"
           R"("owner_surface":"Animation retargeting compatibility","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_dependency_schema_json() {
    return kDependencySchema;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native_payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native_payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
