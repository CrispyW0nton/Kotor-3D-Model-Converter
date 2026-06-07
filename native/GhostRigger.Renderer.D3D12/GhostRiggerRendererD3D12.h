#pragma once

#if defined(_WIN32)
#if defined(RENDERER_D3D12_EXPORTS)
#define GR_RENDERER_D3D12_API __declspec(dllexport)
#else
#define GR_RENDERER_D3D12_API __declspec(dllimport)
#endif
#else
#define GR_RENDERER_D3D12_API
#endif

extern "C" {

GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_version();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_capabilities_json();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_backend_info_json();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_device_requirements_json();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_adapter_probe_json();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_device_readiness_json();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_failure_diagnostics_json();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_dry_run_frame_stats_json();

}
