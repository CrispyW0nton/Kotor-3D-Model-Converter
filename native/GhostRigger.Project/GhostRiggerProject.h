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
}