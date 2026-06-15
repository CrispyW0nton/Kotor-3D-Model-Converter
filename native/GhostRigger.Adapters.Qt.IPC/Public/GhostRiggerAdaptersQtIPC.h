#pragma once

#ifdef GHOSTRIGGER_ADAPTERS_QT_IPC_EXPORTS
#define GHOSTRIGGER_ADAPTERS_QT_IPC_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ADAPTERS_QT_IPC_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ADAPTERS_QT_IPC_API const char* gr_adapters_qt_ipc_version();
GHOSTRIGGER_ADAPTERS_QT_IPC_API const char* gr_adapters_qt_ipc_capabilities_json();
GHOSTRIGGER_ADAPTERS_QT_IPC_API const char* gr_adapters_qt_ipc_owner_boundary_json();
GHOSTRIGGER_ADAPTERS_QT_IPC_API const char* gr_adapters_qt_ipc_dependency_schema_json();
GHOSTRIGGER_ADAPTERS_QT_IPC_API int gr_adapters_qt_ipc_marshal_to_gui_thread(void (*callback)(void*), void* user_data);
}
