#pragma once

#include "GhostRiggerIPC.h"

#include <string>

namespace ghostrigger::domain::core::ipc::contracts {

int port_for_program(const char* program_name);
double default_timeout_seconds();
std::string endpoint_url(int port, const char* action);
std::string request_body_json(const char* sender, const char* action, const char* payload_json);
bool response_is_ok(const char* status);
std::string ping_status_message(const char* program_name, int port, const char* status);

} // namespace ghostrigger::domain::core::ipc::contracts

extern "C" {
GHOSTRIGGER_IPC_API int gr_ipc_port_for_program(const char* program_name);
GHOSTRIGGER_IPC_API double gr_ipc_default_timeout_seconds();
GHOSTRIGGER_IPC_API const char* gr_ipc_endpoint_url(int port, const char* action);
GHOSTRIGGER_IPC_API const char* gr_ipc_request_body_json(const char* sender, const char* action, const char* payload_json);
GHOSTRIGGER_IPC_API int gr_ipc_response_is_ok(const char* status);
GHOSTRIGGER_IPC_API const char* gr_ipc_ping_status_message(const char* program_name, int port, const char* status);
}
