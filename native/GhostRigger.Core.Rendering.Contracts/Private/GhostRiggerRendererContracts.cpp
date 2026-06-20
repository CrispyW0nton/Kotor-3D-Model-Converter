#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerRendererContracts.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kCapabilities =
    R"({"name":"GhostRigger.Core.Rendering.Contracts","version":"0.1.0",)"
    R"("phase":"P1 foundation","renderer_contracts":true,)"
    R"("renderer_neutral":true,"backend_schema":"renderer_backend.v1",)"
    R"("surface_schema":"renderer_surface.v1",)"
    R"("draw_item_schema":"renderer_draw_item.v1",)"
    R"("frame_stats_schema":"renderer_frame_stats.v1",)"
    R"("renderer_capability_contracts_native":true,)"
    R"("renderer_runtime_python_fallback":true,)"
    R"("python_fallback_required":true})";
constexpr const char* kBackendSchema =
    R"({"schema":"renderer_backend.v1","fields":["backend_id","backend_name",)"
    R"("api","device_luid","supports_hardware_rasterization","supports_texture_arrays",)"
    R"("supports_skinned_meshes","supports_pick_pass"]})";
constexpr const char* kSurfaceSchema =
    R"({"schema":"renderer_surface.v1","fields":["surface_id","owner_window_handle",)"
    R"("width","height","dpi_scale","color_format","depth_format","vsync"]})";
constexpr const char* kDrawItemSchema =
    R"({"schema":"renderer_draw_item.v1","fields":["draw_id","mesh_resource_id",)"
    R"("material_resource_id","transform_matrix","skin_palette_resource_id",)"
    R"("selection_id","visible","render_layer"]})";
constexpr const char* kFrameStatsSchema =
    R"({"schema":"renderer_frame_stats.v1","fields":["frame_index","backend_id",)"
    R"("surface_id","draw_count","triangle_count","cpu_submit_ms","gpu_frame_ms"]})";

} // namespace

extern "C" {

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_version() {
    return kVersion;
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_capabilities_json() {
    return kCapabilities;
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_backend_schema_json() {
    return kBackendSchema;
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_surface_schema_json() {
    return kSurfaceSchema;
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_draw_item_schema_json() {
    return kDrawItemSchema;
}

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_frame_stats_schema_json() {
    return kFrameStatsSchema;
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
