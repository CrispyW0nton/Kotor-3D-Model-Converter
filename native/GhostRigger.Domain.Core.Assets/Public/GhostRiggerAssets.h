#pragma once

#ifdef GHOSTRIGGER_ASSETS_EXPORTS
#define GHOSTRIGGER_ASSETS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ASSETS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ASSETS_API const char* gr_assets_version();
GHOSTRIGGER_ASSETS_API const char* gr_assets_capabilities_json();
GHOSTRIGGER_ASSETS_API const char* gr_assets_owner_boundary_json();
GHOSTRIGGER_ASSETS_API const char* gr_assets_dependency_schema_json();
GHOSTRIGGER_ASSETS_API int gr_assets_resource_key(
    const char* name,
    int resource_type,
    char* output,
    unsigned long long output_size
);
GHOSTRIGGER_ASSETS_API const char* gr_assets_texture_name_candidates_json(const char* name);
GHOSTRIGGER_ASSETS_API int gr_assets_extension_to_resource_type(const char* extension);
GHOSTRIGGER_ASSETS_API const char* gr_assets_resource_type_to_extension(int resource_type);
GHOSTRIGGER_ASSETS_API const char* gr_assets_resource_manager_schema_json();
}
