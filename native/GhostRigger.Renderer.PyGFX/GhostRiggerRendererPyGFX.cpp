#include "../GhostRigger.Native.NativeCore/GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerRendererPyGFX.h"

#include "GhostRiggerRendererContracts.h"

#include <string>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kBackendInfo =
    R"({"schema":"renderer_pygfx_backend_info.v1",)"
    R"("backend_id":"renderer_pygfx","backend_name":"GhostRigger Renderer PyGFX",)"
    R"("api":"PyGFX/WGPU","python_adapter":"src.adapters.rendering.pygfx",)"
    R"("diagnostic_only":true,"native_wgpu_device_created":false,)"
    R"("supports_hardware_rasterization":true,"supports_texture_arrays":false,)"
    R"("supports_skinned_meshes":false,"supports_pick_pass":false})";
constexpr const char* kAdapterBridge =
    R"({"schema":"renderer_pygfx_adapter_bridge.v1",)"
    R"("renderer_package":"GhostRigger.Renderer.PyGFX",)"
    R"("contract_package":"GhostRigger.Renderer.Contracts",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("python_adapter_required":true,"native_device_owner":false,)"
    R"("draw_submission_enabled":false,"fallback_backend":"python_pygfx",)"
    R"("failure_points":["python_adapter_missing","qt_surface_missing","native_wgpu_device_disabled"]})";

} // namespace

extern "C" {

GR_RENDERER_PYGFX_API const char* gr_renderer_pygfx_version() {
    return kVersion;
}

GR_RENDERER_PYGFX_API const char* gr_renderer_pygfx_capabilities_json() {
    static const char* prefix =
        R"({"name":"GhostRigger.Renderer.PyGFX","version":"0.1.0",)"
        R"("phase":"P1 foundation","renderer_backend":true,"backend":"pygfx",)"
        R"("diagnostic_only":true,"contract_package":"GhostRigger.Renderer.Contracts",)"
        R"("contract_version":")";
    static thread_local std::string payload;
    payload = prefix;
    payload += gr_renderer_contracts_version();
    payload += R"(","python_adapter_required":true,"native_device_owner":false,)"
               R"("draw_submission_enabled":false,"supports_hardware_rasterization":true})";
    return payload.c_str();
}

GR_RENDERER_PYGFX_API const char* gr_renderer_pygfx_backend_info_json() {
    return kBackendInfo;
}

GR_RENDERER_PYGFX_API const char* gr_renderer_pygfx_adapter_bridge_json() {
    return kAdapterBridge;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native_payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native_payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
