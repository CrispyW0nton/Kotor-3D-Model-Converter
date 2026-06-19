#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsSpriteMaterials.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_sprite_materials_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.SpriteMaterials",)"
    R"("owner_surface":"Sprite Materials",)"
    R"("owner_package":"native/GhostRigger.Core.Tools.SpriteMaterials",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["sprite_material_packet_metadata","alpha_mode_contracts","renderer_material_diagnostics"],)"
    R"("python_owns":["sprite_materials_ui","material_override_authoring","candidate_detection_policy","visible_workflow"],)"
    R"("native_sprite_material_eval_enabled":false})";
constexpr const char* kMaterialPacketSchema =
    R"({"schema":"tools_sprite_materials_material_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.SpriteMaterials",)"
    R"("diagnostic_only":true,"native_sprite_material_eval_enabled":false,)"
    R"("input_packets":["model_handle","mesh_id","texture_name","material_override"],)"
    R"("output_packets":["sprite_classification","alpha_mode","renderer_material_packet","validation_messages"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["model_handle_missing","mesh_handle_missing","native_sprite_material_eval_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_SPRITE_MATERIALS_API const char* gr_tools_sprite_materials_version() {
    return kVersion;
}

GR_TOOLS_SPRITE_MATERIALS_API const char* gr_tools_sprite_materials_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools.SpriteMaterials","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Sprite Materials","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_sprite_material_eval_enabled":false,)"
           R"("capabilities":["owner_boundary","material_packet_schema","alpha_mode_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_SPRITE_MATERIALS_API const char* gr_tools_sprite_materials_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_SPRITE_MATERIALS_API const char* gr_tools_sprite_materials_material_packet_schema_json() {
    return kMaterialPacketSchema;
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
