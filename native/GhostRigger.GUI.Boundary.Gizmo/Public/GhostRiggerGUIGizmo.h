#pragma once

#ifdef GHOSTRIGGER_GUI_GIZMO_EXPORTS
#define GHOSTRIGGER_GUI_GIZMO_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_GIZMO_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_GIZMO_API const char* gr_gui_gizmo_version();
GHOSTRIGGER_GUI_GIZMO_API const char* gr_gui_gizmo_capabilities_json();
GHOSTRIGGER_GUI_GIZMO_API const char* gr_gui_gizmo_owner_boundary_json();
GHOSTRIGGER_GUI_GIZMO_API const char* gr_gui_gizmo_dependency_schema_json();
}