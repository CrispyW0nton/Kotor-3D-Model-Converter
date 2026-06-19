#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsCharacterBuilder.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_character_builder_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.CharacterBuilder",)"
    R"("owner_surface":"Character Studio",)"
    R"("owner_package":"native/GhostRigger.Core.Tools.CharacterBuilder",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["autofit_math_helpers","native_skinning_validation_packets","diagnostic_readback_helpers","character_helper_metadata"],)"
    R"("python_owns":["character_studio_ui","source_asset_selection","game_semantics","save_export_decisions","mcp_validation"],)"
    R"("native_autofit_enabled":false})";
constexpr const char* kAutofitPacketSchema =
    R"({"schema":"tools_character_builder_autofit_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.CharacterBuilder",)"
    R"("diagnostic_only":true,)"
    R"("native_autofit_enabled":false,)"
    R"("input_packets":["source_character_handle","target_skeleton_handle","fit_options","validation_scope"],)"
    R"("output_packets":["autofit_diagnostics","skinning_validation_diagnostics","readback_helper_diagnostics"],)"
    R"("autofit_attempted":false,"autofit_result_count":0,)"
    R"("failure_points":["source_character_missing","target_skeleton_missing","fit_options_missing","native_autofit_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_CHARACTER_BUILDER_API const char* gr_tools_character_builder_version() {
    return kVersion;
}

GR_TOOLS_CHARACTER_BUILDER_API const char* gr_tools_character_builder_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools.CharacterBuilder","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Character Studio",)"
           R"("bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_autofit_enabled":false,)"
           R"("capabilities":["owner_boundary","autofit_packet_schema","skinning_validation_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_CHARACTER_BUILDER_API const char* gr_tools_character_builder_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_CHARACTER_BUILDER_API const char* gr_tools_character_builder_autofit_packet_schema_json() {
    return kAutofitPacketSchema;
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
