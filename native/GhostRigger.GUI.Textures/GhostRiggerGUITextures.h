#pragma once

#ifdef GHOSTRIGGER_GUI_TEXTURES_EXPORTS
#define GHOSTRIGGER_GUI_TEXTURES_API __declspec(dllexport)
#else
#define GHOSTRIGGER_GUI_TEXTURES_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_GUI_TEXTURES_API const char* gr_gui_textures_version();
GHOSTRIGGER_GUI_TEXTURES_API const char* gr_gui_textures_capabilities_json();
GHOSTRIGGER_GUI_TEXTURES_API const char* gr_gui_textures_owner_boundary_json();
GHOSTRIGGER_GUI_TEXTURES_API const char* gr_gui_textures_dependency_schema_json();
}