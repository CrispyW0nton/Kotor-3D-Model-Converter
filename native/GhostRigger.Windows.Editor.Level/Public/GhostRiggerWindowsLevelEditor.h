#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_WINDOWS_LEVEL_EDITOR_EXPORTS)
#define GR_WINDOWS_LEVEL_EDITOR_API __declspec(dllexport)
#else
#define GR_WINDOWS_LEVEL_EDITOR_API __declspec(dllimport)
#endif
#else
#define GR_WINDOWS_LEVEL_EDITOR_API
#endif

extern "C" {

GR_WINDOWS_LEVEL_EDITOR_API const char* gr_windows_level_editor_version();
GR_WINDOWS_LEVEL_EDITOR_API const char* gr_windows_level_editor_capabilities_json();
GR_WINDOWS_LEVEL_EDITOR_API const char* gr_windows_level_editor_owner_boundary_json();
GR_WINDOWS_LEVEL_EDITOR_API const char* gr_windows_level_editor_host_service_schema_json();

}
