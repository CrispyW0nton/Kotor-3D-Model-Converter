#include "GhostRiggerToolsSequenceEditor.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_sequence_editor_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Tools.SequenceEditor",)"
    R"("owner_surface":"Sequence Editor",)"
    R"("owner_package":"native/GhostRigger.Tools.SequenceEditor",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["sequence_packet_metadata","timeline_contracts","keyframe_evaluation_diagnostics"],)"
    R"("python_owns":["sequence_editor_ui","sequence_asset_authoring","scene_binding_policy","visible_workflow"],)"
    R"("native_sequence_eval_enabled":false})";
constexpr const char* kSequencePacketSchema =
    R"({"schema":"tools_sequence_editor_sequence_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Tools.SequenceEditor",)"
    R"("diagnostic_only":true,"native_sequence_eval_enabled":false,)"
    R"("input_packets":["sequence_id","frame","bindings","track_packets"],)"
    R"("output_packets":["evaluated_transforms","evaluated_properties","timeline_diagnostics"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["sequence_handle_missing","binding_snapshot_missing","native_sequence_eval_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_version() {
    return kVersion;
}

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_capabilities_json() {
    return R"({"name":"GhostRigger.Tools.SequenceEditor","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Sequence Editor","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_sequence_eval_enabled":false,)"
           R"("capabilities":["owner_boundary","sequence_packet_schema","timeline_eval_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_sequence_packet_schema_json() {
    return kSequencePacketSchema;
}

}
