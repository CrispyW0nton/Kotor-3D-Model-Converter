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
GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_resource_address_supported_schemes_json();
GR_RUNTIME_SHARED_DESCRIPTORS_API int gr_runtime_shared_descriptors_resource_address_is_supported_scheme(
    const char* scheme
);
GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_resource_address_stable_key(
    const char* scheme,
    const char* game,
    const char* module_id,
    const char* resref,
    const char* restype,
    const char* layer,
    const char* path,
    const char* object_id,
    const char* fragment
);
GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_resource_address_display_name(
    const char* scheme,
    const char* game,
    const char* module_id,
    const char* resref,
    const char* restype,
    const char* layer,
    const char* path,
    const char* object_id,
    const char* fragment
);
GR_RUNTIME_SHARED_DESCRIPTORS_API const char* gr_runtime_shared_descriptors_resource_address_to_json(
    const char* scheme,
    const char* game,
    const char* module_id,
    const char* resref,
    const char* restype,
    const char* layer,
    const char* path,
    const char* object_id,
    const char* fragment
);

}
