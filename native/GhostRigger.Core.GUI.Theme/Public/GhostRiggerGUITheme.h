#pragma once

#ifdef GHOSTRIGGER_GUI_THEME_EXPORTS
#define GHOSTRIGGER_GUI_THEME_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_THEME_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_THEME_API const char* gr_gui_theme_version();
GHOSTRIGGER_GUI_THEME_API const char* gr_gui_theme_capabilities_json();
GHOSTRIGGER_GUI_THEME_API const char* gr_gui_theme_owner_boundary_json();
GHOSTRIGGER_GUI_THEME_API const char* gr_gui_theme_dependency_schema_json();
}