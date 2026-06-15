#pragma once

#ifdef GHOSTRIGGER_LEVEL_EXPORTS
#define GHOSTRIGGER_LEVEL_API __declspec(dllexport)
#else
#define GHOSTRIGGER_LEVEL_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_LEVEL_API const char* gr_level_version();
GHOSTRIGGER_LEVEL_API const char* gr_level_capabilities_json();
GHOSTRIGGER_LEVEL_API const char* gr_level_owner_boundary_json();
GHOSTRIGGER_LEVEL_API const char* gr_level_dependency_schema_json();
}