#pragma once

#ifdef GHOSTRIGGER_GUI_RENDERING_EXPORTS
#define GHOSTRIGGER_GUI_RENDERING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_RENDERING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_RENDERING_API const char* gr_gui_rendering_version();
GHOSTRIGGER_GUI_RENDERING_API const char* gr_gui_rendering_capabilities_json();
GHOSTRIGGER_GUI_RENDERING_API const char* gr_gui_rendering_owner_boundary_json();
GHOSTRIGGER_GUI_RENDERING_API const char* gr_gui_rendering_dependency_schema_json();
}