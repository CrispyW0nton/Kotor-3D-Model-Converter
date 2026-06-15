#pragma once

#ifdef GHOSTRIGGER_ADAPTERS_GPU_EXPORTS
#define GHOSTRIGGER_ADAPTERS_GPU_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ADAPTERS_GPU_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ADAPTERS_GPU_API const char* gr_adapters_gpu_version();
GHOSTRIGGER_ADAPTERS_GPU_API const char* gr_adapters_gpu_capabilities_json();
GHOSTRIGGER_ADAPTERS_GPU_API const char* gr_adapters_gpu_owner_boundary_json();
GHOSTRIGGER_ADAPTERS_GPU_API const char* gr_adapters_gpu_dependency_schema_json();
GHOSTRIGGER_ADAPTERS_GPU_API const char* gr_adapters_gpu_gl_backend_candidates_json(const char* os_name);
GHOSTRIGGER_ADAPTERS_GPU_API int gr_adapters_gpu_light_kind_code(const char* light_kind, int ambient_only);
}
