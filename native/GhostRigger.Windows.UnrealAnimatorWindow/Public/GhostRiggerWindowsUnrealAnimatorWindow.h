#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_WINDOWS_UNREAL_ANIMATOR_WINDOW_EXPORTS)
#define GR_WINDOWS_UNREAL_ANIMATOR_WINDOW_API __declspec(dllexport)
#else
#define GR_WINDOWS_UNREAL_ANIMATOR_WINDOW_API __declspec(dllimport)
#endif
#else
#define GR_WINDOWS_UNREAL_ANIMATOR_WINDOW_API
#endif

extern "C" {

GR_WINDOWS_UNREAL_ANIMATOR_WINDOW_API const char* gr_windows_unreal_animator_window_version();
GR_WINDOWS_UNREAL_ANIMATOR_WINDOW_API const char* gr_windows_unreal_animator_window_capabilities_json();
GR_WINDOWS_UNREAL_ANIMATOR_WINDOW_API const char* gr_windows_unreal_animator_window_owner_boundary_json();
GR_WINDOWS_UNREAL_ANIMATOR_WINDOW_API const char* gr_windows_unreal_animator_window_host_service_schema_json();

}
