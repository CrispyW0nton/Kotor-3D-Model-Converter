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
}