#pragma once

#ifdef GHOSTRIGGER_GUI_SEQUENCE_EDITOR_EXPORTS
#define GHOSTRIGGER_GUI_SEQUENCE_EDITOR_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_SEQUENCE_EDITOR_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_SEQUENCE_EDITOR_API const char* gr_gui_sequence_editor_version();
GHOSTRIGGER_GUI_SEQUENCE_EDITOR_API const char* gr_gui_sequence_editor_capabilities_json();
GHOSTRIGGER_GUI_SEQUENCE_EDITOR_API const char* gr_gui_sequence_editor_owner_boundary_json();
GHOSTRIGGER_GUI_SEQUENCE_EDITOR_API const char* gr_gui_sequence_editor_dependency_schema_json();
}