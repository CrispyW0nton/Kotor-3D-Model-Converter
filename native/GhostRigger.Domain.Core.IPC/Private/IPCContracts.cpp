#include "IPCContracts.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <string>

namespace {

std::string trimmed(const char* value) {
    if (value == nullptr) {
        return {};
    }
    std::string text(value);
    const auto first = std::find_if_not(text.begin(), text.end(), [](unsigned char ch) {
        return std::isspace(ch) != 0;
    });
    const auto last = std::find_if_not(text.rbegin(), text.rend(), [](unsigned char ch) {
        return std::isspace(ch) != 0;
    }).base();
    if (first >= last) {
        return {};
    }
    return std::string(first, last);
}

std::string lower_trimmed(const char* value) {
    std::string text = trimmed(value);
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return text;
}

std::string escape_json_string(const char* value) {
    std::ostringstream out;
    for (const unsigned char ch : std::string(value == nullptr ? "" : value)) {
        switch (ch) {
        case '"':
            out << "\\\"";
            break;
        case '\\':
            out << "\\\\";
            break;
        case '\b':
            out << "\\b";
            break;
        case '\f':
            out << "\\f";
            break;
        case '\n':
            out << "\\n";
            break;
        case '\r':
            out << "\\r";
            break;
        case '\t':
            out << "\\t";
            break;
        default:
            if (ch < 0x20) {
                out << "\\u";
                constexpr char digits[] = "0123456789abcdef";
                out << '0' << '0' << digits[(ch >> 4) & 0x0F] << digits[ch & 0x0F];
            } else {
                out << static_cast<char>(ch);
            }
            break;
        }
    }
    return out.str();
}

std::string normalized_payload_json(const char* payload_json) {
    const std::string payload = trimmed(payload_json);
    if (payload.size() >= 2 && payload.front() == '{' && payload.back() == '}') {
        return payload;
    }
    return "{}";
}

} // namespace

namespace ghostrigger::domain::core::ipc::contracts {

int port_for_program(const char* program_name) {
    const std::string name = lower_trimmed(program_name);
    if (name == "ghostrigger") {
        return 7001;
    }
    if (name == "ghostscripter") {
        return 7002;
    }
    if (name == "gmodular") {
        return 7003;
    }
    return 0;
}

double default_timeout_seconds() {
    return 2.0;
}

std::string endpoint_url(int port, const char* action) {
    std::ostringstream out;
    out << "http://127.0.0.1:" << port << "/api/" << (action == nullptr ? "" : action);
    return out.str();
}

std::string request_body_json(const char* sender, const char* action, const char* payload_json) {
    std::ostringstream out;
    out << R"({"version":"1.0","sender":")" << escape_json_string(sender)
        << R"(","action":")" << escape_json_string(action)
        << R"(","payload":)" << normalized_payload_json(payload_json) << '}';
    return out.str();
}

bool response_is_ok(const char* status) {
    return trimmed(status) == "ok";
}

std::string ping_status_message(const char* program_name, int port, const char* status) {
    const std::string program = trimmed(program_name).empty() ? "Program" : trimmed(program_name);
    const std::string normalized_status = trimmed(status).empty() ? "unavailable" : trimmed(status);
    std::ostringstream out;
    if (normalized_status == "ok") {
        out << program << " is running on port " << port;
        return out.str();
    }
    if (normalized_status == "unavailable") {
        out << program << " is not running - open it to use this feature";
        return out.str();
    }
    out << program << " on port " << port << ": " << normalized_status;
    return out.str();
}

} // namespace ghostrigger::domain::core::ipc::contracts

extern "C" {

GHOSTRIGGER_IPC_API int gr_ipc_port_for_program(const char* program_name) {
    return ghostrigger::domain::core::ipc::contracts::port_for_program(program_name);
}

GHOSTRIGGER_IPC_API double gr_ipc_default_timeout_seconds() {
    return ghostrigger::domain::core::ipc::contracts::default_timeout_seconds();
}

GHOSTRIGGER_IPC_API const char* gr_ipc_endpoint_url(int port, const char* action) {
    static thread_local std::string url;
    url = ghostrigger::domain::core::ipc::contracts::endpoint_url(port, action);
    return url.c_str();
}

GHOSTRIGGER_IPC_API const char* gr_ipc_request_body_json(const char* sender, const char* action, const char* payload_json) {
    static thread_local std::string body;
    body = ghostrigger::domain::core::ipc::contracts::request_body_json(sender, action, payload_json);
    return body.c_str();
}

GHOSTRIGGER_IPC_API int gr_ipc_response_is_ok(const char* status) {
    return ghostrigger::domain::core::ipc::contracts::response_is_ok(status) ? 1 : 0;
}

GHOSTRIGGER_IPC_API const char* gr_ipc_ping_status_message(const char* program_name, int port, const char* status) {
    static thread_local std::string message;
    message = ghostrigger::domain::core::ipc::contracts::ping_status_message(program_name, port, status);
    return message.c_str();
}

}
