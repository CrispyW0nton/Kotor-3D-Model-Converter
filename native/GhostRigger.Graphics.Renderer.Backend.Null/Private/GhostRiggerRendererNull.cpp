#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerRendererNull.h"

#include "GhostRiggerRendererContracts.h"

#include <string>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kBackendInfo =
    R"({"backend_id":"renderer_null","backend_name":"GhostRigger Renderer Null",)"
    R"("api":"null","device_luid":"","supports_hardware_rasterization":false,)"
    R"("supports_texture_arrays":false,"supports_skinned_meshes":false,)"
    R"("supports_pick_pass":false})";
constexpr const char* kDryRunFrameStats =
    R"({"frame_index":0,"backend_id":"renderer_null","surface_id":"diagnostic",)"
    R"("draw_count":0,"triangle_count":0,"cpu_submit_ms":0.0,"gpu_frame_ms":0.0})";

} // namespace

extern "C" {

GR_RENDERER_NULL_API const char* gr_renderer_null_version() {
    return kVersion;
}

GR_RENDERER_NULL_API const char* gr_renderer_null_capabilities_json() {
    static const char* capabilities =
        R"({"name":"GhostRigger.Graphics.Renderer.Backend.Null","version":"0.1.0",)"
        R"("phase":"P1 foundation","renderer_backend":true,"backend":"null",)"
        R"("diagnostic_only":true,"contract_package":"GhostRigger.Graphics.Renderer.Shared.Contracts",)"
        R"("contract_version":")";
    static thread_local std::string payload;
    payload = capabilities;
    payload += gr_renderer_contracts_version();
    payload += R"(","supports_hardware_rasterization":false})";
    return payload.c_str();
}

GR_RENDERER_NULL_API const char* gr_renderer_null_backend_info_json() {
    return kBackendInfo;
}

GR_RENDERER_NULL_API const char* gr_renderer_null_dry_run_frame_stats_json() {
    return kDryRunFrameStats;
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
