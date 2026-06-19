#include "RenderingContracts.h"

#include <algorithm>
#include <cctype>
#include <charconv>
#include <string>

namespace ghostrigger::core::rendering::core::rendering::rendering_contracts {
namespace {

std::string strip_ascii_whitespace(std::string_view value) {
    std::size_t start = 0;
    std::size_t end = value.size();
    while (start < end && std::isspace(static_cast<unsigned char>(value[start]))) {
        ++start;
    }
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }
    return std::string(value.substr(start, end - start));
}

std::string normalized_key(std::string_view value) {
    std::string result;
    const std::string stripped = strip_ascii_whitespace(value);
    result.reserve(stripped.size());
    for (const unsigned char character : stripped) {
        if (character == '-' || character == ' ') {
            result.push_back('_');
        } else {
            result.push_back(static_cast<char>(std::tolower(character)));
        }
    }
    return result;
}

std::string normalized_navigation_key(std::string_view value) {
    std::string result;
    const std::string stripped = strip_ascii_whitespace(value);
    result.reserve(stripped.size());
    for (const unsigned char character : stripped) {
        if (character != ' ' && character != '_') {
            result.push_back(static_cast<char>(std::tolower(character)));
        }
    }
    return result;
}

bool parse_hex_byte(std::string_view value, int& output) noexcept {
    unsigned int parsed = 0;
    const char* first = value.data();
    const char* last = value.data() + value.size();
    const auto result = std::from_chars(first, last, parsed, 16);
    if (result.ec != std::errc{} || result.ptr != last || parsed > 255) {
        return false;
    }
    output = static_cast<int>(parsed);
    return true;
}

} // namespace

RendererBackend normalize_renderer_backend(std::string_view value) noexcept {
    const std::string key = normalized_key(value);
    if (
        key == "auto" || key == "automatic" || key == "modern_gl" || key == "moderngl" ||
        key == "opengl" || key == "gl330" || key == "moderngl_gl330"
    ) {
        return RendererBackend::ModernGL;
    }
    if (
        key == "wgpu" || key == "wgpu_auto" || key == "wgpu_d3d12" || key == "d3d12" ||
        key == "direct3d_wgpu" || key == "direct3d_(wgpu)" || key == "direct3d/wgpu" ||
        key == "direct3d" || key == "wgpu_vulkan" || key == "vulkan" || key == "wgpu_opengl" ||
        key == "native" || key == "native_d3d12" || key == "native/d3d12" ||
        key == "ghostrigger_native" || key == "gr_native" || key == "direct3d_hardware" ||
        key == "d3d_hardware" || key == "direct3d_warp" || key == "d3d_warp"
    ) {
        return RendererBackend::WgpuD3D12;
    }
    if (key == "pygfx" || key == "pygfx_wgpu" || key == "pygfx_(wgpu)" || key == "pygfx/wgpu") {
        return RendererBackend::PygfxWgpu;
    }
    if (key == "null" || key == "null_diagnostic") {
        return RendererBackend::NullDiagnostic;
    }
    return RendererBackend::ModernGL;
}

RendererBackend supported_renderer_backend(std::string_view value) noexcept {
    return normalize_renderer_backend(value);
}

const char* renderer_backend_to_string(RendererBackend backend) noexcept {
    switch (backend) {
    case RendererBackend::ModernGL:
        return "modern_gl";
    case RendererBackend::WgpuD3D12:
        return "wgpu_d3d12";
    case RendererBackend::PygfxWgpu:
        return "pygfx_wgpu";
    case RendererBackend::NullDiagnostic:
        return "null_diagnostic";
    default:
        return "modern_gl";
    }
}

const char* renderer_backend_label(RendererBackend backend) noexcept {
    switch (backend) {
    case RendererBackend::ModernGL:
        return "ModernGL";
    case RendererBackend::WgpuD3D12:
        return "Direct3D (WGPU)";
    case RendererBackend::PygfxWgpu:
        return "pygfx (WGPU)";
    case RendererBackend::NullDiagnostic:
        return "Null Diagnostic";
    default:
        return "ModernGL";
    }
}

ViewportDisplayMode normalize_display_mode(std::string_view value) noexcept {
    const std::string key = normalized_key(value);
    if (key == "wire" || key == "wireframe") {
        return ViewportDisplayMode::Wireframe;
    }
    if (key == "hidden" || key == "hidden_line") {
        return ViewportDisplayMode::HiddenLine;
    }
    if (key == "solid" || key == "flat") {
        return ViewportDisplayMode::Solid;
    }
    if (key == "shaded") {
        return ViewportDisplayMode::Shaded;
    }
    if (key == "smooth" || key == "smooth_shaded") {
        return ViewportDisplayMode::SmoothShaded;
    }
    if (key == "texture" || key == "textured") {
        return ViewportDisplayMode::Textured;
    }
    if (key == "lightmapped" || key == "textured_lightmapped") {
        return ViewportDisplayMode::TexturedLightmapped;
    }
    if (key == "realistic" || key == "full" || key == "full_material") {
        return ViewportDisplayMode::FullMaterial;
    }
    if (key == "bounds" || key == "bounding_box") {
        return ViewportDisplayMode::BoundingBox;
    }
    if (key == "normals" || key == "normals_debug") {
        return ViewportDisplayMode::NormalsDebug;
    }
    if (key == "uv" || key == "uv_debug") {
        return ViewportDisplayMode::UvDebug;
    }
    return ViewportDisplayMode::FullMaterial;
}

const char* display_mode_to_string(ViewportDisplayMode mode) noexcept {
    switch (mode) {
    case ViewportDisplayMode::Wireframe:
        return "wireframe";
    case ViewportDisplayMode::HiddenLine:
        return "hidden_line";
    case ViewportDisplayMode::Solid:
        return "solid";
    case ViewportDisplayMode::Shaded:
        return "shaded";
    case ViewportDisplayMode::SmoothShaded:
        return "smooth_shaded";
    case ViewportDisplayMode::Textured:
        return "textured";
    case ViewportDisplayMode::TexturedLightmapped:
        return "textured_lightmapped";
    case ViewportDisplayMode::FullMaterial:
        return "full_material";
    case ViewportDisplayMode::BoundingBox:
        return "bounding_box";
    case ViewportDisplayMode::NormalsDebug:
        return "normals_debug";
    case ViewportDisplayMode::UvDebug:
        return "uv_debug";
    default:
        return "full_material";
    }
}

const char* display_mode_values_json() noexcept {
    static constexpr const char* kJson =
        R"(["wireframe","hidden_line","solid","shaded","smooth_shaded","textured","textured_lightmapped","full_material","bounding_box","normals_debug","uv_debug"])";
    return kJson;
}

ViewportNavigationProfile normalize_viewport_navigation_profile(std::string_view value) noexcept {
    const std::string key = normalized_navigation_key(value);
    if (key == "3dmax" || key == "3ds" || key == "max" || key == "3dsmax") {
        return ViewportNavigationProfile::ThreeDsMax;
    }
    if (key == "blender") {
        return ViewportNavigationProfile::Blender;
    }
    if (key == "maya") {
        return ViewportNavigationProfile::Maya;
    }
    return ViewportNavigationProfile::ThreeDsMax;
}

const char* viewport_navigation_profile_to_string(ViewportNavigationProfile profile) noexcept {
    switch (profile) {
    case ViewportNavigationProfile::ThreeDsMax:
        return "3dsmax";
    case ViewportNavigationProfile::Blender:
        return "blender";
    case ViewportNavigationProfile::Maya:
        return "3dsmax";
    default:
        return "maya";
    }
}

const char* viewport_navigation_profile_label(ViewportNavigationProfile profile) noexcept {
    switch (profile) {
    case ViewportNavigationProfile::ThreeDsMax:
        return "3ds Max";
    case ViewportNavigationProfile::Blender:
        return "Blender";
    case ViewportNavigationProfile::Maya:
        return "3ds Max";
    default:
        return "Maya";
    }
}

const char* viewport_navigation_profile_summary(ViewportNavigationProfile profile) noexcept {
    switch (profile) {
    case ViewportNavigationProfile::ThreeDsMax:
        return "Alt+MMB orbit, MMB pan, Alt+RMB zoom, mouse wheel zoom";
    case ViewportNavigationProfile::Blender:
        return "MMB orbit, Shift+MMB pan, Ctrl+MMB zoom, mouse wheel zoom";
    case ViewportNavigationProfile::Maya:
        return "Alt+MMB orbit, MMB pan, Alt+RMB zoom, mouse wheel zoom";
    default:
        return "Alt+LMB orbit, Alt+MMB pan, Alt+RMB zoom, mouse wheel zoom";
    }
}

const char* viewport_navigation_profiles_json() noexcept {
    static constexpr const char* kJson =
        R"({"default":"3dsmax","profiles":[)"
        R"({"key":"3dsmax","label":"3ds Max","summary":"Alt+MMB orbit, MMB pan, Alt+RMB zoom, mouse wheel zoom"},)"
        R"({"key":"blender","label":"Blender","summary":"MMB orbit, Shift+MMB pan, Ctrl+MMB zoom, mouse wheel zoom"},)"
        R"({"key":"maya","label":"Maya","summary":"Alt+LMB orbit, Alt+MMB pan, Alt+RMB zoom, mouse wheel zoom"}]})";
    return kJson;
}

std::array<double, 3> hex_to_rgb_float(std::string_view value, std::array<double, 3> fallback) noexcept {
    std::string raw = strip_ascii_whitespace(value);
    while (!raw.empty() && raw.front() == '#') {
        raw.erase(raw.begin());
    }
    if (raw.size() != 6) {
        return fallback;
    }
    int red = 0;
    int green = 0;
    int blue = 0;
    if (!parse_hex_byte(std::string_view(raw).substr(0, 2), red) ||
        !parse_hex_byte(std::string_view(raw).substr(2, 2), green) ||
        !parse_hex_byte(std::string_view(raw).substr(4, 2), blue)) {
        return fallback;
    }
    return {red / 255.0, green / 255.0, blue / 255.0};
}

const char* rendering_contracts_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"rendering_contracts_native.v1",)"
        R"("sources":["src/core/rendering/renderer_backend.py","src/core/rendering/viewport_display.py","src/core/rendering/viewport_navigation.py","src/core/rendering/color_utils.py"],)"
        R"("native_scope":["renderer backend normalization","renderer backend labels","viewport display mode normalization","display mode values","viewport navigation profile normalization","viewport navigation profile labels","viewport navigation profile summaries","hex color to RGB float conversion"],)"
        R"("python_fallback":["ViewportDisplayOptions dataclass state","ViewportNavigationProfile dataclass object construction","full viewport navigation help text","GPU device/resource ownership","mesh/skeleton render data extraction","picking providers","WGPU/ModernGL/PyGFX runtime adapters","software rasterizer pipelines"],)"
        R"("reason_python_fallback":"runtime renderer objects, GPU resources, Python dataclasses, and model-bound render data are still owned by Python or dedicated renderer projects until their subsystems are ported"})";
    return kJson;
}

} // namespace ghostrigger::core::rendering::core::rendering::rendering_contracts
