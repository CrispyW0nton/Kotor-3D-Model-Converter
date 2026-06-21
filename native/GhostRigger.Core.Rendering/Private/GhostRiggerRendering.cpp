#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerRendering.h"
#include "RenderingContracts.h"

#include <array>

namespace rendering_contracts = ghostrigger::core::rendering::core::rendering::rendering_contracts;

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"rendering_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Core.Rendering",)"
    R"("source_package":"src/core/rendering",)"
    R"("owner_surface":"Renderer-neutral core services",)"
    R"("owner_package":"native/GhostRigger.Core.Rendering",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":false,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics","renderer_backend_contracts","viewport_display_contracts","viewport_navigation_contracts","color_conversion_helpers"],)"
    R"("python_owns":["viewport_display_dataclass_state","viewport_navigation_dataclass_state","viewport_navigation_help_text","gpu_resource_runtime","mesh_render_data_extraction","picking_providers","software_rasterizer_pipelines"],)"
    R"("native_implementation_enabled":true})";
constexpr const char* kDependencySchema =
    R"({"schema":"rendering_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Core.Rendering",)"
    R"("source_package":"src/core/rendering",)"
    R"("diagnostic_only":false,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":true,)"
    R"("native_rendering_scope":"backend_display_navigation_color_contracts"})";

} // namespace

extern "C" {

GHOSTRIGGER_RENDERING_API const char* gr_rendering_version() {
    return kVersion;
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Rendering","version":"0.1.0",)"
           R"("phase":"P2 native semantic port","module_package":true,)"
           R"("source_package":"src/core/rendering",)"
           R"("owner_surface":"Renderer-neutral core services","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":false,"native_implementation_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","renderer_backend_contracts","viewport_display_contracts","viewport_navigation_contracts","color_conversion_helpers"],)"
           R"("native_scope":"renderer backend, viewport display, viewport navigation profile, and color conversion contracts",)"
           R"("python_fallback_reason":"GPU resources, renderer adapters, Python display/navigation dataclasses, full navigation help text, picking providers, and mesh/skeleton render data remain Python-owned or renderer-project-owned until those subsystems are ported",)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_normalize_renderer_backend(const char* backend) {
    return rendering_contracts::renderer_backend_to_string(
        rendering_contracts::supported_renderer_backend(backend == nullptr ? "" : backend)
    );
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_renderer_backend_label(const char* backend) {
    return rendering_contracts::renderer_backend_label(
        rendering_contracts::supported_renderer_backend(backend == nullptr ? "" : backend)
    );
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_normalize_display_mode(const char* mode) {
    return rendering_contracts::display_mode_to_string(
        rendering_contracts::normalize_display_mode(mode == nullptr ? "" : mode)
    );
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_display_mode_values_json() {
    return rendering_contracts::display_mode_values_json();
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_normalize_viewport_navigation_profile(const char* profile) {
    return rendering_contracts::viewport_navigation_profile_to_string(
        rendering_contracts::normalize_viewport_navigation_profile(profile == nullptr ? "" : profile)
    );
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_viewport_navigation_profile_label(const char* profile) {
    return rendering_contracts::viewport_navigation_profile_label(
        rendering_contracts::normalize_viewport_navigation_profile(profile == nullptr ? "" : profile)
    );
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_viewport_navigation_profile_summary(const char* profile) {
    return rendering_contracts::viewport_navigation_profile_summary(
        rendering_contracts::normalize_viewport_navigation_profile(profile == nullptr ? "" : profile)
    );
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_viewport_navigation_profiles_json() {
    return rendering_contracts::viewport_navigation_profiles_json();
}

GHOSTRIGGER_RENDERING_API int gr_rendering_hex_to_rgb_float(
    const char* value,
    const double* fallback_rgb,
    double* output_rgb
) {
    if (output_rgb == nullptr) {
        return 0;
    }
    std::array<double, 3> fallback = {0.0, 0.0, 0.0};
    if (fallback_rgb != nullptr) {
        fallback = {fallback_rgb[0], fallback_rgb[1], fallback_rgb[2]};
    }
    const auto converted = rendering_contracts::hex_to_rgb_float(value == nullptr ? "" : value, fallback);
    output_rgb[0] = converted[0];
    output_rgb[1] = converted[1];
    output_rgb[2] = converted[2];
    return 1;
}

GHOSTRIGGER_RENDERING_API const char* gr_rendering_contracts_schema_json() {
    return rendering_contracts::rendering_contracts_schema_json();
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
