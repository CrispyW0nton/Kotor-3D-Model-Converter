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
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_queue_swap_chain_readiness_json();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_descriptor_allocator_readiness_json(void* context);
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_command_list_readiness_json(void* context);
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_failure_diagnostics_json();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_dry_run_frame_stats_json();
GR_RENDERER_D3D12_API void* gr_renderer_d3d12_create_diagnostic_context();
GR_RENDERER_D3D12_API const char* gr_renderer_d3d12_diagnostic_context_json(void* context);
GR_RENDERER_D3D12_API void gr_renderer_d3d12_destroy_diagnostic_context(void* context);

}
