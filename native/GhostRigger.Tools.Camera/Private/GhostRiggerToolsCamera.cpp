#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsCamera.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_camera_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Tools.Camera",)"
    R"("owner_surface":"Camera",)"
    R"("owner_package":"native/GhostRigger.Tools.Camera",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["camera_packet_metadata","projection_contracts","camera_validation_diagnostics"],)"
    R"("python_owns":["camera_ui","camera_scene_objects","viewport_camera_binding","visible_workflow"],)"
    R"("native_camera_eval_enabled":false})";
constexpr const char* kCameraPacketSchema =
    R"({"schema":"tools_camera_camera_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Tools.Camera",)"
    R"("diagnostic_only":true,"native_camera_eval_enabled":false,)"
    R"("input_packets":["camera_id","transform","lens","clip_planes","target_binding"],)"
    R"("output_packets":["view_matrix","projection_matrix","validation_messages"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["camera_handle_missing","scene_handle_missing","native_camera_eval_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_CAMERA_API const char* gr_tools_camera_version() {
    return kVersion;
}

GR_TOOLS_CAMERA_API const char* gr_tools_camera_capabilities_json() {
    return R"({"name":"GhostRigger.Tools.Camera","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Camera","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_camera_eval_enabled":false,)"
           R"("capabilities":["owner_boundary","camera_packet_schema","projection_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_CAMERA_API const char* gr_tools_camera_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_CAMERA_API const char* gr_tools_camera_camera_packet_schema_json() {
    return kCameraPacketSchema;
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
