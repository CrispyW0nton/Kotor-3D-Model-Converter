#pragma once

#ifdef GHOSTRIGGER_WORKBENCH_EXPORTS
#define GHOSTRIGGER_WORKBENCH_API __declspec(dllexport)
#else
#define GHOSTRIGGER_WORKBENCH_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_WORKBENCH_API const char* gr_workbench_version();
GHOSTRIGGER_WORKBENCH_API const char* gr_workbench_capabilities_json();
GHOSTRIGGER_WORKBENCH_API const char* gr_workbench_owner_boundary_json();
GHOSTRIGGER_WORKBENCH_API const char* gr_workbench_dependency_schema_json();
}