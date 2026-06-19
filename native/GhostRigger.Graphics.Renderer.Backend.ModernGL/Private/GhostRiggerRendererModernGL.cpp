#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerRendererModernGL.h"

#include "GhostRiggerRendererContracts.h"

#include <cmath>
#include <iomanip>
#include <sstream>
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
    R"("renderer_package":"GhostRigger.Graphics.Renderer.Backend.ModernGL",)"
    R"("contract_package":"GhostRigger.Graphics.Renderer.Shared.Contracts",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("python_adapter_required":true,"native_device_owner":false,)"
    R"("draw_submission_enabled":false,"fallback_backend":"python_moderngl",)"
    R"("failure_points":["python_adapter_missing","qt_surface_missing","native_context_disabled"]})";

double finite_or_zero(double value) {
    return std::isfinite(value) ? value : 0.0;
}

int non_negative_or_zero(int value) {
    return value > 0 ? value : 0;
}

std::string json_escape(const char* text) {
    if (text == nullptr || *text == '\0') {
        return "";
    }
    std::string out;
    for (const char* cursor = text; *cursor != '\0'; ++cursor) {
        const unsigned char ch = static_cast<unsigned char>(*cursor);
        switch (ch) {
        case '\\':
            out += "\\\\";
            break;
        case '"':
            out += "\\\"";
            break;
        case '\b':
            out += "\\b";
            break;
        case '\f':
            out += "\\f";
            break;
        case '\n':
            out += "\\n";
            break;
        case '\r':
            out += "\\r";
            break;
        case '\t':
            out += "\\t";
            break;
        default:
            if (ch < 0x20) {
                std::ostringstream escaped;
                escaped << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(ch);
                out += escaped.str();
            } else {
                out += static_cast<char>(ch);
            }
        }
    }
    return out;
}

} // namespace

extern "C" {

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_version() {
    return kVersion;
}

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_capabilities_json() {
    static const char* prefix =
        R"({"name":"GhostRigger.Graphics.Renderer.Backend.ModernGL","version":"0.1.0",)"
        R"("phase":"P1 foundation","renderer_backend":true,"backend":"moderngl",)"
        R"("diagnostic_only":true,"contract_package":"GhostRigger.Graphics.Renderer.Shared.Contracts",)"
        R"("contract_version":")";
    static thread_local std::string payload;
    payload = prefix;
    payload += gr_renderer_contracts_version();
    payload += R"(","python_adapter_required":true,"native_device_owner":false,)"
               R"("draw_submission_enabled":false,"supports_hardware_rasterization":true,)"
               R"("diagnostic_contracts":["frame_diagnostics"]})";
    return payload.c_str();
}

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_backend_info_json() {
    return kBackendInfo;
}

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_adapter_bridge_json() {
    return kAdapterBridge;
}

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_frame_diagnostics_json(
    int available,
    int version_code,
    const char* gpu,
    const char* vendor,
    double frame_time_ms,
    double upload_ms,
    double draw_ms,
    double readback_ms,
    int triangle_count,
    int mesh_cache_size,
    int texture_cache_size
) {
    static thread_local std::string payload;
    std::ostringstream out;
    out << std::fixed << std::setprecision(3);
    out << R"({"schema":"renderer_moderngl_frame_diagnostics.v1",)";
    out << R"("name":"ModernGL",)";
    out << R"("backend_id":"moderngl_gl330",)";
    out << R"("available":)" << (available ? "true" : "false") << ',';
    out << R"("api":"OpenGL",)";
    out << R"("backend":"ModernGL",)";
    out << R"("mature_material_path":true,)";
    out << R"("native_diagnostics":true,)";
    if (version_code >= 0) {
        out << R"("version_code":)" << version_code << ',';
    } else {
        out << R"("version_code":null,)";
    }
    out << R"("gpu":")" << json_escape(gpu) << R"(",)";
    out << R"("vendor":")" << json_escape(vendor) << R"(",)";
    out << R"("performance":{)";
    out << R"("frame_time_ms":)" << finite_or_zero(frame_time_ms) << ',';
    out << R"("upload_ms":)" << finite_or_zero(upload_ms) << ',';
    out << R"("draw_ms":)" << finite_or_zero(draw_ms) << ',';
    out << R"("readback_ms":)" << finite_or_zero(readback_ms);
    out << R"(},)";
    out << R"("triangle_count":)" << non_negative_or_zero(triangle_count) << ',';
    out << R"("mesh_cache_size":)" << non_negative_or_zero(mesh_cache_size) << ',';
    out << R"("texture_cache_size":)" << non_negative_or_zero(texture_cache_size);
    out << '}';
    payload = out.str();
    return payload.c_str();
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
