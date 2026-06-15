#pragma once

#if defined(_WIN32)
#if defined(RENDERER_MODERNGL_EXPORTS)
#define GR_RENDERER_MODERNGL_API __declspec(dllexport)
#else
#define GR_RENDERER_MODERNGL_API __declspec(dllimport)
#endif
#else
#define GR_RENDERER_MODERNGL_API
#endif

extern "C" {

GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_version();
GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_capabilities_json();
GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_backend_info_json();
GR_RENDERER_MODERNGL_API const char* gr_renderer_moderngl_adapter_bridge_json();
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
);

}
