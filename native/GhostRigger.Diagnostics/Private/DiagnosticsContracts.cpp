#include "DiagnosticsContracts.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <string>
#include <string_view>

namespace ghostrigger::diagnostics::core::diagnostics::contracts {
namespace {

constexpr std::array<const char*, 34> kScriptFields = {{
    "onacquireitem",
    "onactivateitem",
    "onattacked",
    "onblocked",
    "onclosed",
    "ondamaged",
    "ondeath",
    "ondialog",
    "ondisarm",
    "onenddialog",
    "onenter",
    "onexit",
    "onfailtoopen",
    "onheartbeat",
    "onmeleeattacked",
    "onnotice",
    "onopen",
    "onperception",
    "onphysicalattacked",
    "onrest",
    "onrested",
    "onspawn",
    "onspellcastat",
    "ontraptriggered",
    "onunaquireitem",
    "onunacquireitem",
    "onused",
    "onuserdefined",
    "mod_onacquiritem",
    "mod_onactivateit",
    "mod_oncliententr",
    "mod_onclientlev",
    "mod_onheartbeat",
    "mod_onmodload",
}};

constexpr std::array<const char*, 5> kExtraScriptFields = {{
    "mod_onmodstart",
    "mod_onplayerdye",
    "mod_onplrdth",
    "mod_onplrrest",
    "mod_onspawnbtndn",
}};

constexpr std::array<const char*, 1> kFinalScriptFields = {{
    "mod_onunacquir",
}};

constexpr std::array<const char*, 4> kDialogFields = {{
    "conversation",
    "conversationresref",
    "dialog",
    "dialogresref",
}};

std::string trim(std::string value) {
    const auto first = std::find_if_not(value.begin(), value.end(), [](unsigned char ch) { return std::isspace(ch) != 0; });
    const auto last = std::find_if_not(value.rbegin(), value.rend(), [](unsigned char ch) { return std::isspace(ch) != 0; }).base();
    if (first >= last) {
        return {};
    }
    return std::string(first, last);
}

std::string lower_trim(const char* value) {
    std::string text = trim(value == nullptr ? std::string() : std::string(value));
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return text;
}

bool starts_with(std::string_view text, std::string_view prefix) noexcept {
    return text.size() >= prefix.size() && text.substr(0, prefix.size()) == prefix;
}

template <typename Rows>
bool contains(const Rows& rows, std::string_view value) noexcept {
    for (const char* row : rows) {
        if (value == row) {
            return true;
        }
    }
    return false;
}

std::string json_escape(std::string_view value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (const char ch : value) {
        switch (ch) {
        case '\\':
            out += "\\\\";
            break;
        case '"':
            out += "\\\"";
            break;
        case '\n':
            out += "\\n";
            break;
        case '\r':
            out += "\\r";
            break;
        case '\t':
            out += "\\t";
            break;
        default:
            out.push_back(ch);
            break;
        }
    }
    return out;
}

std::string text_or_empty(const char* value) {
    return value == nullptr ? std::string() : std::string(value);
}

std::string upper(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) { return static_cast<char>(std::toupper(ch)); });
    return value;
}

std::string reference_json(
    const char* kind,
    const char* resref,
    const char* restype,
    const char* owner_type,
    int owner_index,
    const char* field,
    const char* source_label) {
    std::string out = R"({"kind":")";
    out += json_escape(text_or_empty(kind));
    out += R"(","resref":")";
    out += json_escape(text_or_empty(resref));
    out += R"(","restype":")";
    out += json_escape(text_or_empty(restype));
    out += R"(","owner_type":")";
    out += json_escape(text_or_empty(owner_type));
    out += R"(","owner_index":)";
    out += std::to_string(owner_index);
    out += R"(,"field":")";
    out += json_escape(text_or_empty(field));
    out += R"(","source_label":")";
    out += json_escape(text_or_empty(source_label));
    out += R"("})";
    return out;
}

} // namespace

const char* normalize_resref(const char* value) noexcept {
    thread_local std::string text;
    text = lower_trim(value);
    const auto dot = text.rfind('.');
    if (dot != std::string::npos) {
        text = text.substr(0, dot);
    }
    if (text.size() > 16) {
        text.resize(16);
    }
    return text.c_str();
}

const char* normalize_restype(const char* value) noexcept {
    thread_local std::string text;
    text = lower_trim(value);
    while (!text.empty() && text.front() == '.') {
        text.erase(text.begin());
    }
    return text.c_str();
}

int is_script_field(const char* field_name) noexcept {
    const std::string key = lower_trim(field_name);
    return contains(kScriptFields, key) || contains(kExtraScriptFields, key) || contains(kFinalScriptFields, key) ||
                   starts_with(key, "script") || starts_with(key, "mod_on")
        ? 1
        : 0;
}

int is_dialog_field(const char* field_name) noexcept {
    return contains(kDialogFields, lower_trim(field_name)) ? 1 : 0;
}

const char* missing_reference_issue_json(
    const char* kind,
    const char* resref,
    const char* restype,
    const char* owner_type,
    int owner_index,
    const char* field,
    const char* source_label) noexcept {
    thread_local std::string out;
    const std::string kind_text = text_or_empty(kind);
    const std::string resref_text = text_or_empty(resref);
    const std::string restype_text = text_or_empty(restype);
    const std::string owner_type_text = text_or_empty(owner_type);
    const std::string source_label_text = text_or_empty(source_label);
    const std::string ref = reference_json(kind, resref, restype, owner_type, owner_index, field, source_label);

    if (kind_text == "template") {
        out = R"({"severity":"error","code":"MISSING_TEMPLATE","message":")";
        out += json_escape(owner_type_text + " " + std::to_string(owner_index) + " references missing " + upper(restype_text) + " template '" + resref_text + "'.");
        out += R"(","reference":)";
        out += ref;
        out += R"(,"action":"Add the template to the module static archive or choose an existing template."})";
        return out.c_str();
    }
    if (kind_text == "dialog") {
        out = R"({"severity":"warning","code":"UNRESOLVED_DIALOG","message":")";
        out += json_escape(source_label_text + " references dialog '" + resref_text + ".dlg', but it was not found in the hydrated module resources.");
        out += R"(","reference":)";
        out += ref;
        out += R"(,"action":"Verify the DLG exists in the module, Override, or base game resources before save."})";
        return out.c_str();
    }
    out = R"({"severity":"warning","code":"UNRESOLVED_SCRIPT","message":")";
    out += json_escape(source_label_text + " references script '" + resref_text + "', but no matching NCS/NSS was found in the hydrated module resources.");
    out += R"(","reference":)";
    out += ref;
    out += R"(,"action":"Compile or include the script, or verify it exists in global game resources."})";
    return out.c_str();
}

const char* diagnostics_contracts_schema_json() noexcept {
    return R"({"schema":"diagnostics_contracts_native.v1",)"
           R"("source":["src/core/diagnostics/module_reference_safety.py"],)"
           R"("native_scope":["module reference resref normalization","module reference resource-type normalization","script field classification","dialog field classification","missing-reference issue construction"],)"
           R"("python_fallback":["hydrated module traversal","available resource indexing","resolver callbacks","MDL header diagnostics","crash sentinel file IO","logging integration","CharacterScene validation service"],)"
           R"("reason_python_fallback":"Hydrated module traversal, resolver callbacks, model diagnostics, file IO, logging, and character-scene validation depend on runtime Python objects or game/model data that need dedicated validated subsystem ports"})";
}

} // namespace ghostrigger::diagnostics::core::diagnostics::contracts

extern "C" {

__declspec(dllexport) const char* gr_diagnostics_normalize_resref(const char* value) {
    return ghostrigger::diagnostics::core::diagnostics::contracts::normalize_resref(value);
}

__declspec(dllexport) const char* gr_diagnostics_normalize_restype(const char* value) {
    return ghostrigger::diagnostics::core::diagnostics::contracts::normalize_restype(value);
}

__declspec(dllexport) int gr_diagnostics_is_script_field(const char* field_name) {
    return ghostrigger::diagnostics::core::diagnostics::contracts::is_script_field(field_name);
}

__declspec(dllexport) int gr_diagnostics_is_dialog_field(const char* field_name) {
    return ghostrigger::diagnostics::core::diagnostics::contracts::is_dialog_field(field_name);
}

__declspec(dllexport) const char* gr_diagnostics_missing_reference_issue_json(
    const char* kind,
    const char* resref,
    const char* restype,
    const char* owner_type,
    int owner_index,
    const char* field,
    const char* source_label) {
    return ghostrigger::diagnostics::core::diagnostics::contracts::missing_reference_issue_json(
        kind,
        resref,
        restype,
        owner_type,
        owner_index,
        field,
        source_label);
}

__declspec(dllexport) const char* gr_diagnostics_contracts_schema_json() {
    return ghostrigger::diagnostics::core::diagnostics::contracts::diagnostics_contracts_schema_json();
}

}
