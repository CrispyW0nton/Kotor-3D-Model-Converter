#pragma once

#ifdef GHOSTRIGGER_WORKFLOW_EXPORTS
#define GHOSTRIGGER_WORKFLOW_API __declspec(dllexport)
#else
#define GHOSTRIGGER_WORKFLOW_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_version();
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_capabilities_json();
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_owner_boundary_json();
GHOSTRIGGER_WORKFLOW_API const char* gr_workflow_dependency_schema_json();
}