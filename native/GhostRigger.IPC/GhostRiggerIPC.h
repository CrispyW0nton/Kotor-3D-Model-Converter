#pragma once

#ifdef GHOSTRIGGER_IPC_EXPORTS
#define GHOSTRIGGER_IPC_API __declspec(dllexport)
#else
#define GHOSTRIGGER_IPC_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_IPC_API const char* gr_ipc_version();
GHOSTRIGGER_IPC_API const char* gr_ipc_capabilities_json();
GHOSTRIGGER_IPC_API const char* gr_ipc_owner_boundary_json();
GHOSTRIGGER_IPC_API const char* gr_ipc_dependency_schema_json();
}