#pragma once

#if defined(_WIN32)
#if defined(RENDERER_CONTRACTS_EXPORTS)
#define GR_RENDERER_CONTRACTS_API __declspec(dllexport)
#else
#define GR_RENDERER_CONTRACTS_API __declspec(dllimport)
#endif
#else
#define GR_RENDERER_CONTRACTS_API
#endif

extern "C" {

GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_version();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_capabilities_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_backend_schema_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_surface_schema_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_draw_item_schema_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_frame_stats_schema_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_normalize_display_mode(const char* value);
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_moderngl_display_modes_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_wgpu_display_modes_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_wgpu_fallback_display_modes_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_diagnostic_display_modes_json();
GR_RENDERER_CONTRACTS_API const char* gr_renderer_contracts_status_text(
    int available,
    int diagnostic_only,
    const char* reason
);
GR_RENDERER_CONTRACTS_API int gr_renderer_contracts_supports_display_mode(
    int available,
    int diagnostic_only,
    const char* supported_modes,
    const char* mode
);

}
