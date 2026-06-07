#pragma once

#ifdef GHOSTRIGGER_GUI_LIGHTING_EXPORTS
#define GHOSTRIGGER_GUI_LIGHTING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_LIGHTING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_LIGHTING_API const char* gr_gui_lighting_version();
GHOSTRIGGER_GUI_LIGHTING_API const char* gr_gui_lighting_capabilities_json();
GHOSTRIGGER_GUI_LIGHTING_API const char* gr_gui_lighting_owner_boundary_json();
GHOSTRIGGER_GUI_LIGHTING_API const char* gr_gui_lighting_dependency_schema_json();
}