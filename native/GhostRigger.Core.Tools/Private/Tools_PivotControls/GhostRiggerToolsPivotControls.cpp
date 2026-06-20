#include "GhostRiggerPythonPayloadResource.h"
#include "Tools_PivotControls/GhostRiggerToolsPivotControls.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_pivot_controls_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("owner_surface":"PivotControls",)"
    R"("owner_package":"native/GhostRigger.Core.Tools",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["pivot_packet_metadata","transform_preservation_contracts","adjust_pivot_diagnostics","pivot_command_contract"],)"
    R"("python_owns":["pivot_controls_ui","scene_object_transform_policy","undo_redo_integration","visible_workflow"],)"
    R"("native_pivot_edit_enabled":false,"native_command_contract_enabled":true})";
constexpr const char* kPivotPacketSchema =
    R"({"schema":"tools_pivot_controls_pivot_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("diagnostic_only":true,"native_pivot_edit_enabled":false,)"
    R"("input_packets":["object_id","pivot_delta","reference_mode","preserve_world_geometry"],)"
    R"("output_packets":["transform_delta","pivot_result","validation_messages"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["object_handle_missing","transform_snapshot_missing","native_pivot_edit_disabled"]})";
constexpr const char* kCommandSchema =
    R"({"schema":"tools_pivot_controls_command_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("owner_package":"native/GhostRigger.Core.Tools",)"
    R"("native_command_contract_enabled":true,)"
    R"("native_pivot_edit_enabled":false,)"
    R"("runtime_bridge":"ipc:pivot_command",)"
    R"("modes":["affect_pivot_only","affect_object_only","affect_hierarchy_only"],)"
    R"("actions":["status","set_mode","center_to_object","align_to_object","align_to_world","reset_pivot"],)"
    R"("packet_keys":["command","mode","action"],)"
    R"("result_keys":["ok","command","mode","selection_count","pivot","message","warnings","errors"],)"
    R"("requires_visible_app":true})";

} // namespace

extern "C" {

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_version() {
    return kVersion;
}

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"PivotControls","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_pivot_edit_enabled":false,)"
           R"("native_command_contract_enabled":true,)"
           R"("capabilities":["owner_boundary","pivot_packet_schema","pivot_command_schema","adjust_pivot_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_pivot_packet_schema_json() {
    return kPivotPacketSchema;
}

GR_TOOLS_PIVOT_CONTROLS_API const char* gr_tools_pivot_controls_command_schema_json() {
    return kCommandSchema;
}

}

