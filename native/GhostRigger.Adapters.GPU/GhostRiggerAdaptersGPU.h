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
}