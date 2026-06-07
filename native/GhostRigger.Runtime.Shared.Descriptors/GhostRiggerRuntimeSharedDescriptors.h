#pragma once

#if defined(_WIN32)
#if defined(RUNTIME_SHARED_DESCRIPTORS_EXPORTS)
#define GR_RUNTIME_SHARED_DESCRIPTORS_API __declspec(dllexport)
#else
#define GR_RUNTIME_SHARED_DESCRIPTORS_API __declspec(dllimport)
#endif
#else
#define GR_RUNTIME_SHARED_DESCRIPTORS_API
#endif

extern "C" {

GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_version();
GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_capabilities_json();
GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_mesh_schema_json();
GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_material_schema_json();
GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_frame_schema_json();

}
