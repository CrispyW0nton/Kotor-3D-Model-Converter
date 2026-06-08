#pragma once

#ifdef GHOSTRIGGER_RENDERING_EXPORTS
#define GHOSTRIGGER_RENDERING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_RENDERING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_RENDERING_API const char* gr_rendering_version();
GHOSTRIGGER_RENDERING_API const char* gr_rendering_capabilities_json();
GHOSTRIGGER_RENDERING_API const char* gr_rendering_owner_boundary_json();
GHOSTRIGGER_RENDERING_API const char* gr_rendering_dependency_schema_json();
GHOSTRIGGER_RENDERING_API const char* gr_rendering_normalize_renderer_backend(const char* backend);
GHOSTRIGGER_RENDERING_API const char* gr_rendering_renderer_backend_label(const char* backend);
GHOSTRIGGER_RENDERING_API const char* gr_rendering_normalize_display_mode(const char* mode);
GHOSTRIGGER_RENDERING_API const char* gr_rendering_display_mode_values_json();
GHOSTRIGGER_RENDERING_API const char* gr_rendering_normalize_viewport_navigation_profile(const char* profile);
GHOSTRIGGER_RENDERING_API const char* gr_rendering_viewport_navigation_profile_label(const char* profile);
GHOSTRIGGER_RENDERING_API const char* gr_rendering_viewport_navigation_profile_summary(const char* profile);
GHOSTRIGGER_RENDERING_API const char* gr_rendering_viewport_navigation_profiles_json();
GHOSTRIGGER_RENDERING_API int gr_rendering_hex_to_rgb_float(
    const char* value,
    const double* fallback_rgb,
    double* output_rgb
);
GHOSTRIGGER_RENDERING_API const char* gr_rendering_contracts_schema_json();
}
