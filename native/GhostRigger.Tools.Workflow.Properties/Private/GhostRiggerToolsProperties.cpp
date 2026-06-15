#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsProperties.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_properties_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Tools.Workflow.Properties",)"
    R"("owner_surface":"Properties",)"
    R"("owner_package":"native/GhostRigger.Tools.Workflow.Properties",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["property_packet_metadata","property_validation_contracts","edit_delta_diagnostics"],)"
    R"("python_owns":["properties_ui","scene_object_edit_policy","undo_redo_integration","visible_workflow"],)"
    R"("native_property_edit_enabled":false})";
constexpr const char* kPropertyPacketSchema =
    R"({"schema":"tools_properties_property_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Tools.Workflow.Properties",)"
    R"("diagnostic_only":true,"native_property_edit_enabled":false,)"
    R"("input_packets":["object_id","property_path","candidate_value","edit_context"],)"
    R"("output_packets":["validation_messages","normalized_value","edit_delta"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["object_handle_missing","property_path_unknown","native_property_edit_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_PROPERTIES_API const char* gr_tools_properties_version() {
    return kVersion;
}

GR_TOOLS_PROPERTIES_API const char* gr_tools_properties_capabilities_json() {
    return R"({"name":"GhostRigger.Tools.Workflow.Properties","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Properties","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_property_edit_enabled":false,)"
           R"("capabilities":["owner_boundary","property_packet_schema","property_validation_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_PROPERTIES_API const char* gr_tools_properties_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_PROPERTIES_API const char* gr_tools_properties_property_packet_schema_json() {
    return kPropertyPacketSchema;
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
