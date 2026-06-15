#pragma once

#ifdef GHOSTRIGGER_PROJECT_EXPORTS
#define GHOSTRIGGER_PROJECT_API __declspec(dllexport)
#else
#define GHOSTRIGGER_PROJECT_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_PROJECT_API const char* gr_project_version();
GHOSTRIGGER_PROJECT_API const char* gr_project_capabilities_json();
GHOSTRIGGER_PROJECT_API const char* gr_project_owner_boundary_json();
GHOSTRIGGER_PROJECT_API const char* gr_project_dependency_schema_json();
GHOSTRIGGER_PROJECT_API const char* gr_project_resource_address_supported_schemes_json();
GHOSTRIGGER_PROJECT_API int gr_project_resource_address_is_supported_scheme(const char* scheme);
GHOSTRIGGER_PROJECT_API const char* gr_project_resource_address_stable_key(
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
GHOSTRIGGER_PROJECT_API const char* gr_project_resource_address_display_name(
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
GHOSTRIGGER_PROJECT_API const char* gr_project_resource_address_to_json(
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
GHOSTRIGGER_PROJECT_API const char* gr_project_resource_address_contracts_schema_json();
}
