#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsPivotControls.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_pivot_controls_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Tools.PivotControls",)"
    R"("owner_surface":"PivotControls",)"
    R"("owner_package":"native/GhostRigger.Tools.PivotControls",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["pivot_packet_metadata","transform_preservation_contracts","adjust_pivot_diagnostics"],)"
    R"("python_owns":["pivot_controls_ui","scene_object_transform_policy","undo_redo_integration","visible_workflow"],)"
    R"("native_pivot_edit_enabled":false})";
constexpr const char* kPivotPacketSchema =
    R"({"schema":"tools_pivot_controls_pivot_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Tools.PivotControls",)"
    R"("diagnostic_only":true,"native_pivot_edit_enabled":false,)"
    R"("input_packets":["object_id","pivot_delta","reference_mode","preserve_world_geometry"],)"
    R"("output_packets":["transform_delta","pivot_result","validation_messages"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["object_handle_missing","transform_snapshot_missing","native_pivot_edit_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_version() {
    return kVersion;
}

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_capabilities_json() {
    return R"({"name":"GhostRigger.Tools.PivotControls","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"PivotControls","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_pivot_edit_enabled":false,)"
           R"("capabilities":["owner_boundary","pivot_packet_schema","adjust_pivot_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_pivot_packet_schema_json() {
    return kPivotPacketSchema;
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
