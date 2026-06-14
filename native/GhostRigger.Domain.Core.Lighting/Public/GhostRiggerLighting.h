#pragma once

#ifdef GHOSTRIGGER_LIGHTING_EXPORTS
#define GHOSTRIGGER_LIGHTING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_LIGHTING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_LIGHTING_API const char* gr_lighting_version();
GHOSTRIGGER_LIGHTING_API const char* gr_lighting_capabilities_json();
GHOSTRIGGER_LIGHTING_API const char* gr_lighting_owner_boundary_json();
GHOSTRIGGER_LIGHTING_API const char* gr_lighting_dependency_schema_json();
}