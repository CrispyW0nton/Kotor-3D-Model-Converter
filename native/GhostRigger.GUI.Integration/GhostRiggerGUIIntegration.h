#pragma once

#ifdef GHOSTRIGGER_GUI_INTEGRATION_EXPORTS
#define GHOSTRIGGER_GUI_INTEGRATION_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_INTEGRATION_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_INTEGRATION_API const char* gr_gui_integration_version();
GHOSTRIGGER_GUI_INTEGRATION_API const char* gr_gui_integration_capabilities_json();
GHOSTRIGGER_GUI_INTEGRATION_API const char* gr_gui_integration_owner_boundary_json();
GHOSTRIGGER_GUI_INTEGRATION_API const char* gr_gui_integration_dependency_schema_json();
}