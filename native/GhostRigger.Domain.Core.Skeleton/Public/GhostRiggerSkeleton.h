#pragma once

#ifdef GHOSTRIGGER_SKELETON_EXPORTS
#define GHOSTRIGGER_SKELETON_API __declspec(dllexport)
#else
#define GHOSTRIGGER_SKELETON_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_SKELETON_API const char* gr_skeleton_version();
GHOSTRIGGER_SKELETON_API const char* gr_skeleton_capabilities_json();
GHOSTRIGGER_SKELETON_API const char* gr_skeleton_owner_boundary_json();
GHOSTRIGGER_SKELETON_API const char* gr_skeleton_dependency_schema_json();
}