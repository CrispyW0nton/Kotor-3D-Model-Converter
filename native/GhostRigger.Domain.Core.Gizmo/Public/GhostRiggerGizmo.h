#pragma once

#ifdef GHOSTRIGGER_GIZMO_EXPORTS
#define GHOSTRIGGER_GIZMO_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GIZMO_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_version();
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_capabilities_json();
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_owner_boundary_json();
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_dependency_schema_json();
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_normalize_mode(const char* mode);
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_cycle_mode(const char* mode);
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_mode_values_json();
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_normalize_transform_space(const char* space);
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_transform_space_values_json();
GHOSTRIGGER_GIZMO_API const char* gr_gizmo_mode_contracts_schema_json();
GHOSTRIGGER_GIZMO_API int gr_gizmo_resolve_origin(
    const double* position,
    const double* pivot_world,
    const double* gizmo_world,
    int has_pivot_world,
    int has_gizmo_world,
    int is_helper_object,
    int affect_pivot_only,
    double* out_origin
);
}
