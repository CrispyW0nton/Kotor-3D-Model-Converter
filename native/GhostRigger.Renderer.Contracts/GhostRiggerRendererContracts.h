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

}
