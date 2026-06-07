#pragma once

#ifdef GHOSTRIGGER_GUI_CAMERA_EXPORTS
#define GHOSTRIGGER_GUI_CAMERA_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_CAMERA_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_CAMERA_API const char* gr_gui_camera_version();
GHOSTRIGGER_GUI_CAMERA_API const char* gr_gui_camera_capabilities_json();
GHOSTRIGGER_GUI_CAMERA_API const char* gr_gui_camera_owner_boundary_json();
GHOSTRIGGER_GUI_CAMERA_API const char* gr_gui_camera_dependency_schema_json();
}