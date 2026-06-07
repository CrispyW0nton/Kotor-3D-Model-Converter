#pragma once

#if defined(_WIN32)
#if defined(RENDERER_NULL_EXPORTS)
#define GR_RENDERER_NULL_API __declspec(dllexport)
#else
#define GR_RENDERER_NULL_API __declspec(dllimport)
#endif
#else
#define GR_RENDERER_NULL_API
#endif

extern "C" {

GR_RENDERER_NULL_API const char* gr_renderer_null_version();
GR_RENDERER_NULL_API const char* gr_renderer_null_capabilities_json();
GR_RENDERER_NULL_API const char* gr_renderer_null_backend_info_json();
GR_RENDERER_NULL_API const char* gr_renderer_null_dry_run_frame_stats_json();

}
