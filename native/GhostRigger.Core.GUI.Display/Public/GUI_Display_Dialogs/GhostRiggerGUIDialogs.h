#pragma once

#ifdef GHOSTRIGGER_GUI_DIALOGS_EXPORTS
#define GHOSTRIGGER_GUI_DIALOGS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_DIALOGS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_DIALOGS_API const char* gr_gui_dialogs_version();
GHOSTRIGGER_GUI_DIALOGS_API const char* gr_gui_dialogs_capabilities_json();
GHOSTRIGGER_GUI_DIALOGS_API const char* gr_gui_dialogs_owner_boundary_json();
GHOSTRIGGER_GUI_DIALOGS_API const char* gr_gui_dialogs_dependency_schema_json();
}