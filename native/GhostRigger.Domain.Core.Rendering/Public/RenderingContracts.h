#pragma once

#include <array>
#include <string_view>

namespace ghostrigger::domain::core::rendering::core::rendering::rendering_contracts {

enum class RendererBackend {
    ModernGL,
    WgpuD3D12,
    PygfxWgpu,
    NullDiagnostic,
};

enum class ViewportDisplayMode {
    Wireframe,
    HiddenLine,
    Solid,
    Shaded,
    SmoothShaded,
    Textured,
    TexturedLightmapped,
    FullMaterial,
    BoundingBox,
    NormalsDebug,
    UvDebug,
};

enum class ViewportNavigationProfile {
    ThreeDsMax,
    Blender,
    Maya,
};

RendererBackend normalize_renderer_backend(std::string_view value) noexcept;
RendererBackend supported_renderer_backend(std::string_view value) noexcept;
const char* renderer_backend_to_string(RendererBackend backend) noexcept;
const char* renderer_backend_label(RendererBackend backend) noexcept;
ViewportDisplayMode normalize_display_mode(std::string_view value) noexcept;
const char* display_mode_to_string(ViewportDisplayMode mode) noexcept;
const char* display_mode_values_json() noexcept;
ViewportNavigationProfile normalize_viewport_navigation_profile(std::string_view value) noexcept;
const char* viewport_navigation_profile_to_string(ViewportNavigationProfile profile) noexcept;
const char* viewport_navigation_profile_label(ViewportNavigationProfile profile) noexcept;
const char* viewport_navigation_profile_summary(ViewportNavigationProfile profile) noexcept;
const char* viewport_navigation_profiles_json() noexcept;
std::array<double, 3> hex_to_rgb_float(std::string_view value, std::array<double, 3> fallback) noexcept;
const char* rendering_contracts_schema_json() noexcept;

} // namespace ghostrigger::domain::core::rendering::core::rendering::rendering_contracts
