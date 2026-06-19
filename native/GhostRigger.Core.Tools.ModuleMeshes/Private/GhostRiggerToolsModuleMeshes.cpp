#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsModuleMeshes.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_module_meshes_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.ModuleMeshes",)"
    R"("owner_surface":"Module Meshes",)"
    R"("owner_package":"native/GhostRigger.Core.Tools.ModuleMeshes",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_mesh_packet_metadata","visibility_toggle_contracts","renderer_selection_diagnostics"],)"
    R"("python_owns":["module_meshes_ui","module_scene_lifetime","viewport_selection_sync","visible_workflow"],)"
    R"("native_mesh_index_enabled":false})";
constexpr const char* kMeshPacketSchema =
    R"({"schema":"tools_module_meshes_mesh_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools.ModuleMeshes",)"
    R"("diagnostic_only":true,"native_mesh_index_enabled":false,)"
    R"("input_packets":["module_id","mesh_filter","selection_ids","visibility_flags"],)"
    R"("output_packets":["mesh_rows","selection_summary","visibility_deltas"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["module_handle_missing","mesh_index_missing","native_mesh_index_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_MODULE_MESHES_API const char* gr_tools_module_meshes_version() {
    return kVersion;
}

GR_TOOLS_MODULE_MESHES_API const char* gr_tools_module_meshes_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools.ModuleMeshes","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Module Meshes","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_mesh_index_enabled":false,)"
           R"("capabilities":["owner_boundary","mesh_packet_schema","visibility_toggle_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_MODULE_MESHES_API const char* gr_tools_module_meshes_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_MODULE_MESHES_API const char* gr_tools_module_meshes_mesh_packet_schema_json() {
    return kMeshPacketSchema;
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
