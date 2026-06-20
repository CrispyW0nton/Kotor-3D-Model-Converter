#pragma once

#ifdef GHOSTRIGGER_CORE_RENDERING_GPU_EXPORTS
#define GHOSTRIGGER_CORE_RENDERING_GPU_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CORE_RENDERING_GPU_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_version();
GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_capabilities_json();
GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_owner_boundary_json();
GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_dependency_schema_json();
GHOSTRIGGER_CORE_RENDERING_GPU_API const char* gr_core_rendering_gpu_gl_backend_candidates_json(const char* os_name);
GHOSTRIGGER_CORE_RENDERING_GPU_API int gr_core_rendering_gpu_light_kind_code(const char* light_kind, int ambient_only);
}
