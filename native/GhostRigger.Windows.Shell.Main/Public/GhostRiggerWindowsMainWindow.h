#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_WINDOWS_MAIN_WINDOW_EXPORTS)
#define GR_WINDOWS_MAIN_WINDOW_API __declspec(dllexport)
#else
#define GR_WINDOWS_MAIN_WINDOW_API __declspec(dllimport)
#endif
#else
#define GR_WINDOWS_MAIN_WINDOW_API
#endif

extern "C" {

typedef void(__cdecl* GRWindowsMainPrelaunchTaskCallback)(int task_index);
typedef void(__cdecl* GRWindowsMainPrelaunchStatusCallback)(const char* title, const char* detail);

GR_WINDOWS_MAIN_WINDOW_API const char* gr_windows_main_window_version();
GR_WINDOWS_MAIN_WINDOW_API const char* gr_windows_main_window_capabilities_json();
GR_WINDOWS_MAIN_WINDOW_API const char* gr_windows_main_window_owner_boundary_json();
GR_WINDOWS_MAIN_WINDOW_API const char* gr_windows_main_window_host_service_schema_json();
GR_WINDOWS_MAIN_WINDOW_API int gr_windows_main_window_run_prelaunch_tasks(
    int task_count,
    GRWindowsMainPrelaunchTaskCallback task_callback,
    GRWindowsMainPrelaunchStatusCallback status_callback
);

}
