#include "GhostRiggerRendererD3D12.h"

#include "GhostRiggerRendererContracts.h"

#include <string>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kBackendInfo =
    R"({"backend_id":"renderer_d3d12","backend_name":"GhostRigger Renderer D3D12",)"
    R"("api":"d3d12","device_luid":"","supports_hardware_rasterization":true,)"
    R"("supports_texture_arrays":true,"supports_skinned_meshes":true,)"
    R"("supports_pick_pass":true,"diagnostic_only":true})";
constexpr const char* kDeviceRequirements =
    R"({"schema":"renderer_d3d12_device_requirements.v1",)"
    R"("minimum_feature_level":"12_0","requires_dxgi_factory":true,)"
    R"("requires_command_queue":true,"requires_swap_chain":true,)"
    R"("requires_descriptor_heaps":["cbv_srv_uav","rtv","dsv"],)"
    R"("phase":"P1 diagnostic boundary"})";
constexpr const char* kDryRunFrameStats =
    R"({"frame_index":0,"backend_id":"renderer_d3d12","surface_id":"diagnostic",)"
    R"("draw_count":0,"triangle_count":0,"cpu_submit_ms":0.0,"gpu_frame_ms":0.0})";

} // namespace

extern "C" {

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_version() {
    return kVersion;
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_capabilities_json() {
    static const char* capabilities =
        R"({"name":"GhostRigger.Renderer.D3D12","version":"0.1.0",)"
        R"("phase":"P1 foundation","renderer_backend":true,"backend":"d3d12",)"
        R"("diagnostic_only":true,"contract_package":"GhostRigger.Renderer.Contracts",)"
        R"("contract_version":")";
    static thread_local std::string payload;
    payload = capabilities;
    payload += gr_renderer_contracts_version();
    payload += R"(","supports_hardware_rasterization":true,)"
               R"("supports_texture_arrays":true,"supports_skinned_meshes":true,)"
               R"("supports_pick_pass":true})";
    return payload.c_str();
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_backend_info_json() {
    return kBackendInfo;
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_device_requirements_json() {
    return kDeviceRequirements;
}

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_dry_run_frame_stats_json() {
    return kDryRunFrameStats;
}

}
