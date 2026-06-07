#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerScene.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"scene_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Scene",)"
    R"("source_package":"src/core/scene",)"
    R"("owner_surface":"Main Viewport / KMAX scene services",)"
    R"("owner_package":"native/GhostRigger.Scene",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"scene_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Scene",)"
    R"("source_package":"src/core/scene",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";

} // namespace

extern "C" {

GHOSTRIGGER_SCENE_API const char* gr_scene_version() {
    return kVersion;
}

GHOSTRIGGER_SCENE_API const char* gr_scene_capabilities_json() {
    return R"({"name":"GhostRigger.Scene","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/scene",)"
           R"("owner_surface":"Main Viewport / KMAX scene services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_SCENE_API const char* gr_scene_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_SCENE_API const char* gr_scene_dependency_schema_json() {
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
