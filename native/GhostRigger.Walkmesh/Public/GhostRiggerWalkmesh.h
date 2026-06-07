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
}