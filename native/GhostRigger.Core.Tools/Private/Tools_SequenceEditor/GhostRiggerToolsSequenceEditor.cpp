#include "GhostRiggerPythonPayloadResource.h"
#include "Tools_SequenceEditor/GhostRiggerToolsSequenceEditor.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_sequence_editor_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("owner_surface":"Sequence Editor",)"
    R"("owner_package":"native/GhostRigger.Core.Tools",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","sequence_packet_metadata","sequence_contracts"],)"
    R"("python_owns":["sequence_editor_ui","sequence_asset_authoring","scene_binding_policy","recursive_value_interpolation","visible_workflow"],)"
    R"("native_sequence_eval_enabled":false})";
constexpr const char* kSequencePacketSchema =
    R"({"schema":"tools_sequence_editor_sequence_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("diagnostic_only":false,"native_sequence_eval_enabled":false,)"
    R"("input_packets":["sequence_id","frame","bindings","track_packets"],)"
    R"("output_packets":["evaluated_transforms","evaluated_properties","timeline_diagnostics"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("native_scope":["interpolation modes","easing curves","numeric/boolean interpolation","frame-time math"],)"
    R"("failure_points":["sequence_handle_missing","binding_snapshot_missing","track_runtime_python_owned"]})";

} // namespace

extern "C" {

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_version() {
    return kVersion;
}

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools","version":"0.1.0",)"
           R"("phase":"P2 merged sequence runtime","tool_package":true,)"
           R"("owner_surface":"Sequence Editor","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_sequence_eval_enabled":false,)"
           R"("capabilities":["owner_boundary","sequence_packet_schema","timeline_eval_placeholder","sequence_contracts"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_SEQUENCE_EDITOR_API const char* gr_tools_sequence_editor_sequence_packet_schema_json() {
    return kSequencePacketSchema;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native::core::payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native::core::payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
