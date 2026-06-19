#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsLighting.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_lighting_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.Lighting",)"
    R"("owner_surface":"Lighting",)"
    R"("owner_package":"native/GhostRigger.Core.Tools.Lighting",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["light_packet_metadata","light_validation_contracts","renderer_lighting_diagnostics"],)"
    R"("python_owns":["lighting_ui","scene_light_lifetime","theme_layout_state","visible_workflow"],)"
    R"("native_light_eval_enabled":false})";
constexpr const char* kLightPacketSchema =
    R"({"schema":"tools_lighting_light_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.Lighting",)"
    R"("diagnostic_only":true,"native_light_eval_enabled":false,)"
    R"("input_packets":["light_id","light_type","transform","color_intensity","shadow_flags"],)"
    R"("output_packets":["normalized_light","renderer_light_packet","validation_messages"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["light_handle_missing","scene_handle_missing","native_light_eval_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_LIGHTING_API const char* gr_tools_lighting_version() {
    return kVersion;
}

GR_TOOLS_LIGHTING_API const char* gr_tools_lighting_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools.Lighting","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Lighting","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_light_eval_enabled":false,)"
           R"("capabilities":["owner_boundary","light_packet_schema","renderer_lighting_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_LIGHTING_API const char* gr_tools_lighting_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_LIGHTING_API const char* gr_tools_lighting_light_packet_schema_json() {
    return kLightPacketSchema;
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
