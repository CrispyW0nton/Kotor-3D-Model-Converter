#include "UnavailableScriptCompiler.h"

#include <sstream>
#include <string>

namespace {

std::string text_or_empty(const char* value) {
    return value == nullptr ? std::string() : std::string(value);
}

std::string reason_or_default(const char* reason) {
    const std::string text = text_or_empty(reason);
    return text.empty() ? ghostrigger::adapters::scripting::core::default_unavailable_reason() : text;
}

std::string escape_json_string(const std::string& value) {
    std::ostringstream out;
    for (const unsigned char ch : value) {
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
                constexpr char digits[] = "0123456789abcdef";
                out << "\\u00" << digits[(ch >> 4) & 0x0F] << digits[ch & 0x0F];
            } else {
                out << static_cast<char>(ch);
            }
            break;
        }
    }
    return out.str();
}

void append_json_string_field(std::ostringstream& out, const char* name, const std::string& value) {
    out << '"' << name << R"(":")" << escape_json_string(value) << '"';
}

} // namespace

namespace ghostrigger::adapters::scripting::core {

const char* default_unavailable_reason() {
    return "No NWScript compiler adapter is configured.";
}

std::string unavailable_validation_issue_json(const char* source, const char* game, const char* reason) {
    const std::string source_text = text_or_empty(source);
    const std::string game_text = text_or_empty(game);
    const std::string reason_text = reason_or_default(reason);

    std::ostringstream out;
    out << '{';
    append_json_string_field(out, "severity", "blocking");
    out << ',';
    append_json_string_field(out, "subsystem", "script");
    out << ',';
    append_json_string_field(out, "code", "script.compiler.unavailable");
    out << ',';
    append_json_string_field(out, "message", reason_text);
    out << R"(,"target":null,"details":{)";
    append_json_string_field(out, "source", source_text);
    out << ',';
    append_json_string_field(out, "game", game_text);
    out << "}}";
    return out.str();
}

std::string unavailable_compile_result_json(const char* source, const char* game, const char* reason) {
    const std::string source_text = text_or_empty(source);
    const std::string game_text = text_or_empty(game);
    const std::string reason_text = reason_or_default(reason);

    std::ostringstream out;
    out << '{';
    append_json_string_field(out, "source", source_text);
    out << R"(,"output_hex":"","report":{"source":"script.compiler","issues":[)"
        << unavailable_validation_issue_json(source, game, reason)
        << R"(]},"metadata":{)";
    out << R"("available":false,)";
    append_json_string_field(out, "reason", reason_text);
    out << ',';
    append_json_string_field(out, "game", game_text);
    out << "}}";
    return out.str();
}

} // namespace ghostrigger::adapters::scripting::core

extern "C" {

GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_unavailable_default_reason() {
    return ghostrigger::adapters::scripting::core::default_unavailable_reason();
}

GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_unavailable_issue_json(
    const char* source,
    const char* game,
    const char* reason
) {
    static thread_local std::string issue;
    issue = ghostrigger::adapters::scripting::core::unavailable_validation_issue_json(source, game, reason);
    return issue.c_str();
}

GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_unavailable_compile_result_json(
    const char* source,
    const char* game,
    const char* reason
) {
    static thread_local std::string result;
    result = ghostrigger::adapters::scripting::core::unavailable_compile_result_json(source, game, reason);
    return result.c_str();
}

}
