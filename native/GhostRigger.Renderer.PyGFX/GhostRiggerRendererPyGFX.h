#pragma once

#if defined(_WIN32)
#if defined(RENDERER_PYGFX_EXPORTS)
#define GR_RENDERER_PYGFX_API __declspec(dllexport)
#else
#define GR_RENDERER_PYGFX_API __declspec(dllimport)
#endif
#else
#define GR_RENDERER_PYGFX_API
#endif

extern "C" {

GR_RENDERER_PYGFX_API const char* gr_renderer_pygfx_version();
GR_RENDERER_PYGFX_API const char* gr_renderer_pygfx_capabilities_json();
GR_RENDERER_PYGFX_API const char* gr_renderer_pygfx_backend_info_json();
GR_RENDERER_PYGFX_API const char* gr_renderer_pygfx_adapter_bridge_json();

}
