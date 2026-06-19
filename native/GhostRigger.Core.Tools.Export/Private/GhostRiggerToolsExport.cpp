#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsExport.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_export_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.Export",)"
    R"("owner_surface":"Export and validation workflow",)"
    R"("owner_package":"native/GhostRigger.Core.Tools.Export",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["native_readback_helpers","packed_buffer_diagnostics","export_preflight_packets","validation_helper_metadata"],)"
    R"("python_owns":["export_decisions","file_format_policy","game_resource_semantics","write_prompts","dirty_scene_safety","final_writer_orchestration"],)"
    R"("native_write_enabled":false})";
constexpr const char* kPreflightPacketSchema =
    R"({"schema":"tools_export_preflight_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.Export",)"
    R"("diagnostic_only":true,)"
    R"("native_write_enabled":false,)"
    R"("input_packets":["scene_handle","resource_address","target_game","export_options","validation_scope"],)"
    R"("output_packets":["packed_buffer_diagnostics","resource_reference_diagnostics","writer_readiness_diagnostics","reload_comparison_placeholder"],)"
    R"("preflight_attempted":false,"preflight_result_count":0,)"
    R"("failure_points":["scene_missing","resource_address_missing","target_game_missing","native_writer_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_EXPORT_API const char* gr_tools_export_version() {
    return kVersion;
}

GR_TOOLS_EXPORT_API const char* gr_tools_export_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools.Export","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Export and validation workflow",)"
           R"("bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_write_enabled":false,)"
           R"("capabilities":["owner_boundary","preflight_packet_schema","readback_diagnostics_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_EXPORT_API const char* gr_tools_export_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_EXPORT_API const char* gr_tools_export_preflight_packet_schema_json() {
    return kPreflightPacketSchema;
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
