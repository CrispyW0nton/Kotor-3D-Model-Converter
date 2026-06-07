#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerNativeCoreDiagnostics.h"

#include <algorithm>
#include <string>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kCapabilities =
    R"({"name":"GhostRigger.Native.NativeCore.Diagnostics","version":"0.1.0",)"
    R"("phase":"P1 foundation","shared_diagnostics":true,"renderer_neutral":true,)"
    R"("record_schema":"native_diagnostic_record.v1"})";
constexpr const char* kRecordSchema =
    R"({"schema":"native_diagnostic_record.v1","fields":["severity","system","code","message"],)"
    R"("severity":{"debug":0,"info":1,"warning":2,"error":3}})";

thread_local std::string g_record_buffer;

std::string safe_text(const char* text) {
    return text == nullptr ? std::string{} : std::string{text};
}

std::string escape_json(std::string_view text) {
    std::string escaped;
    escaped.reserve(text.size());
    for (const char ch : text) {
        switch (ch) {
        case '\\':
            escaped += "\\\\";
            break;
        case '"':
            escaped += "\\\"";
            break;
        case '\n':
            escaped += "\\n";
            break;
        case '\r':
            escaped += "\\r";
            break;
        case '\t':
            escaped += "\\t";
            break;
        default:
            escaped += ch;
            break;
        }
    }
    return escaped;
}

} // namespace

extern "C" {

GR_NATIVE_CORE_DIAGNOSTICS_API const char* gr_native_core_diagnostics_version() {
    return kVersion;
}

GR_NATIVE_CORE_DIAGNOSTICS_API const char* gr_native_core_diagnostics_capabilities_json() {
    return kCapabilities;
}

GR_NATIVE_CORE_DIAGNOSTICS_API const char* gr_native_core_diagnostics_record_schema_json() {
    return kRecordSchema;
}

GR_NATIVE_CORE_DIAGNOSTICS_API const char* gr_native_core_diagnostics_make_record_json(
    int severity,
    const char* system,
    const char* code,
    const char* message) {
    const int clamped_severity = std::clamp(severity, 0, 3);
    g_record_buffer = R"({"severity":)" + std::to_string(clamped_severity) +
        R"(,"system":")" + escape_json(safe_text(system)) +
        R"(","code":")" + escape_json(safe_text(code)) +
        R"(","message":")" + escape_json(safe_text(message)) + R"("})";
    return g_record_buffer.c_str();
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native_payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native_payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
