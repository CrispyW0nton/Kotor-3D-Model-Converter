#pragma once

#ifdef GHOSTRIGGER_GUI_PANELS_EXPORTS
#define GHOSTRIGGER_GUI_PANELS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_PANELS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_PANELS_API const char* gr_gui_panels_version();
GHOSTRIGGER_GUI_PANELS_API const char* gr_gui_panels_capabilities_json();
GHOSTRIGGER_GUI_PANELS_API const char* gr_gui_panels_owner_boundary_json();
GHOSTRIGGER_GUI_PANELS_API const char* gr_gui_panels_dependency_schema_json();
}