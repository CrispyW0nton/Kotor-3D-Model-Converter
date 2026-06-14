#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_SCENE_INFORMATION_EXPORTS)
#define GR_TOOLS_SCENE_INFORMATION_API __declspec(dllexport)
#else
#define GR_TOOLS_SCENE_INFORMATION_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_SCENE_INFORMATION_API
#endif

extern "C" {

GR_TOOLS_SCENE_INFORMATION_API const char* gr_tools_scene_information_version();
GR_TOOLS_SCENE_INFORMATION_API const char* gr_tools_scene_information_capabilities_json();
GR_TOOLS_SCENE_INFORMATION_API const char* gr_tools_scene_information_owner_boundary_json();
GR_TOOLS_SCENE_INFORMATION_API const char* gr_tools_scene_information_scene_summary_schema_json();

}
