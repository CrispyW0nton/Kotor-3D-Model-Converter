#pragma once

#ifdef GHOSTRIGGER_SCENE_EXPORTS
#define GHOSTRIGGER_SCENE_API __declspec(dllexport)
#else
#define GHOSTRIGGER_SCENE_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_SCENE_API const char* gr_scene_version();
GHOSTRIGGER_SCENE_API const char* gr_scene_capabilities_json();
GHOSTRIGGER_SCENE_API const char* gr_scene_owner_boundary_json();
GHOSTRIGGER_SCENE_API const char* gr_scene_dependency_schema_json();
}