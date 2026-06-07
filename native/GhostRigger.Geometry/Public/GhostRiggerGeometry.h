#pragma once

#ifdef GHOSTRIGGER_GEOMETRY_EXPORTS
#define GHOSTRIGGER_GEOMETRY_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GEOMETRY_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GEOMETRY_API const char* gr_geometry_version();
GHOSTRIGGER_GEOMETRY_API const char* gr_geometry_capabilities_json();
GHOSTRIGGER_GEOMETRY_API const char* gr_geometry_owner_boundary_json();
GHOSTRIGGER_GEOMETRY_API const char* gr_geometry_dependency_schema_json();
}