#pragma once

#ifdef GHOSTRIGGER_CORE_QT_IPC_EXPORTS
#define GHOSTRIGGER_CORE_QT_IPC_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CORE_QT_IPC_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CORE_QT_IPC_API const char* gr_core_qt_ipc_version();
GHOSTRIGGER_CORE_QT_IPC_API const char* gr_core_qt_ipc_capabilities_json();
GHOSTRIGGER_CORE_QT_IPC_API const char* gr_core_qt_ipc_owner_boundary_json();
GHOSTRIGGER_CORE_QT_IPC_API const char* gr_core_qt_ipc_dependency_schema_json();
GHOSTRIGGER_CORE_QT_IPC_API int gr_core_qt_ipc_marshal_to_gui_thread(void (*callback)(void*), void* user_data);
}
