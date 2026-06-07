#include "GhostRiggerRendererModernGL.h"

#include "GhostRiggerRendererContracts.h"

#include <string>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kBackendInfo =
    R"({"schema":"renderer_moderngl_backend_info.v1",)"
    R"("backend_id":"renderer_moderngl","backend_name":"GhostRigger Renderer ModernGL",)"
    R"("api":"ModernGL","python_adapter":"src.adapters.rendering.moderngl",)"
    R"("diagnostic_only":true,"native_context_created":false,)"
    R"("supports_hardware_rasterization":true,"supports_texture_arrays":false,)"
    R"("supports_skinned_meshes":false,"supports_pick_pass":false})";
constexpr const char* kAdapterBridge =
    R"({"schema":"renderer_moderngl_adapter_bridge.v1",)"
    R"("renderer_package":"GhostRigger.Renderer.ModernGL",)"
    R"("contract_package":"GhostRigger.Renderer.Contracts",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("python_adapter_required":true,"native_device_owner":false,)"
    R"("draw_submission_enabled":false,"fallback_backend":"python_moderngl",)"
    R"("failure_points":["python_adapter_missing","qt_surface_missing","native_context_disabled"]})";

} // namespace

extern "C" {

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_version() {
    return kVersion;
}

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_capabilities_json() {
    static const char* prefix =
        R"({"name":"GhostRigger.Renderer.ModernGL","version":"0.1.0",)"
        R"("phase":"P1 foundation","renderer_backend":true,"backend":"moderngl",)"
        R"("diagnostic_only":true,"contract_package":"GhostRigger.Renderer.Contracts",)"
        R"("contract_version":")";
    static thread_local std::string payload;
    payload = prefix;
    payload += gr_renderer_contracts_version();
    payload += R"(","python_adapter_required":true,"native_device_owner":false,)"
               R"("draw_submission_enabled":false,"supports_hardware_rasterization":true})";
    return payload.c_str();
}

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_backend_info_json() {
    return kBackendInfo;
}

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_adapter_bridge_json() {
    return kAdapterBridge;
}

}
