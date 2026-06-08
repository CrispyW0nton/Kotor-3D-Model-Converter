#pragma once

#ifdef GHOSTRIGGER_WALKMESH_EXPORTS
#define GHOSTRIGGER_WALKMESH_API __declspec(dllexport)
#else
#define GHOSTRIGGER_WALKMESH_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_version();
GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_capabilities_json();
GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_owner_boundary_json();
GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_dependency_schema_json();
GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_surface_name(int surface_id);
GHOSTRIGGER_WALKMESH_API void gr_walkmesh_surface_color(int surface_id, double* r, double* g, double* b, double* a);
GHOSTRIGGER_WALKMESH_API int gr_walkmesh_surface_is_walkable(int surface_id);
GHOSTRIGGER_WALKMESH_API int gr_walkmesh_surface_is_non_walkable(int surface_id);
GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_fbx_material_name(int surface_id);
GHOSTRIGGER_WALKMESH_API void gr_walkmesh_fbx_material_diffuse(int surface_id, double* r, double* g, double* b);
GHOSTRIGGER_WALKMESH_API const char* gr_walkmesh_surface_contracts_schema_json();
}
