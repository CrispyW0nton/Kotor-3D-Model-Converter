#pragma once

#ifdef GHOSTRIGGER_RESOURCES_EXPORTS
#define GHOSTRIGGER_RESOURCES_API __declspec(dllexport)
#else
#define GHOSTRIGGER_RESOURCES_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_RESOURCES_API const char* gr_resources_version();
GHOSTRIGGER_RESOURCES_API const char* gr_resources_capabilities_json();
GHOSTRIGGER_RESOURCES_API const char* gr_resources_owner_boundary_json();
GHOSTRIGGER_RESOURCES_API const char* gr_resources_dependency_schema_json();
}