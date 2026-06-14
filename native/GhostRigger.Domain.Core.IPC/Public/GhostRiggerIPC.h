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
GHOSTRIGGER_IPC_API int gr_ipc_port_for_program(const char* program_name);
GHOSTRIGGER_IPC_API double gr_ipc_default_timeout_seconds();
GHOSTRIGGER_IPC_API const char* gr_ipc_endpoint_url(int port, const char* action);
GHOSTRIGGER_IPC_API const char* gr_ipc_request_body_json(const char* sender, const char* action, const char* payload_json);
GHOSTRIGGER_IPC_API int gr_ipc_response_is_ok(const char* status);
GHOSTRIGGER_IPC_API const char* gr_ipc_ping_status_message(const char* program_name, int port, const char* status);
}
