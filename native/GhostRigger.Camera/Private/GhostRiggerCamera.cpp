#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerCamera.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"camera_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Camera",)"
    R"("source_package":"src/core/camera",)"
    R"("owner_surface":"Camera services",)"
    R"("owner_package":"native/GhostRigger.Camera",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","camera_math_contracts","camera_validation_contracts","render_settings_contracts","preset_contracts"],)"
    R"("python_owns":["image_save_encoding","render_manifest_writes","camera_manager_object_lifetime","viewport_adapter_state","qt_workflow_orchestration"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"camera_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Camera",)"
    R"("source_package":"src/core/camera",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("python_fallback_reason":"Image encoding, manifest persistence, live camera object ownership, viewport adapter state, and Qt workflow orchestration remain Python-owned until dedicated runtime slices are ported"})";

} // namespace

extern "C" {

GHOSTRIGGER_CAMERA_API const char* gr_camera_version() {
    return kVersion;
}

GHOSTRIGGER_CAMERA_API const char* gr_camera_capabilities_json() {
    return R"({"name":"GhostRigger.Camera","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/core/camera",)"
           R"("owner_surface":"Camera services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("camera_contracts_native":true,"camera_runtime_python_fallback":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","camera_math_contracts","camera_validation_contracts","render_settings_contracts","preset_contracts"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_CAMERA_API const char* gr_camera_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_CAMERA_API const char* gr_camera_dependency_schema_json() {
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
