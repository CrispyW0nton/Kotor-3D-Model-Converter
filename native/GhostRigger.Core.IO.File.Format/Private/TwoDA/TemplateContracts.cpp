#include "2DA/TemplateContracts.h"

#include <algorithm>
#include <cctype>
#include <string>
#include <string_view>
#include <vector>

namespace ghostrigger::core::templates::core::templates::contracts {
namespace {

std::string trim(std::string value) {
    const auto first = std::find_if_not(value.begin(), value.end(), [](unsigned char ch) { return std::isspace(ch) != 0; });
    const auto last = std::find_if_not(value.rbegin(), value.rend(), [](unsigned char ch) { return std::isspace(ch) != 0; }).base();
    if (first >= last) {
        return {};
    }
    return std::string(first, last);
}

std::string upper_trim(const char* value) {
    std::string text = trim(value == nullptr ? std::string() : std::string(value));
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char ch) { return static_cast<char>(std::toupper(ch)); });
    return text;
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

std::string json_array(const std::vector<std::string>& values) {
    std::string out = "[";
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i != 0) {
            out += ",";
        }
        out += "\"";
        out += json_escape(values[i]);
        out += "\"";
    }
    out += "]";
    return out;
}

} // namespace

const char* normalize_game_version(const char* game_version) noexcept {
    return upper_trim(game_version) == "K2" ? "K2" : "K1";
}

int humanoid_bone_count(const char* game_version) noexcept {
    return normalize_game_version(game_version)[1] == '2' ? 71 : 64;
}

int humanoid_animation_slot_count(const char* game_version) noexcept {
    return normalize_game_version(game_version)[1] == '2' ? 76 : 56;
}

const char* humanoid_rig_source(const char* game_version) noexcept {
    return normalize_game_version(game_version)[1] == '2'
        ? "Based on KotOR 2 c_female02 / S_Female02 skeleton"
        : "Based on KotOR 1 S_Male02 / S_Female02 skeleton";
}

const char* detect_twoda_format(const unsigned char* data, unsigned int size) noexcept {
    if (data == nullptr || size == 0) {
        return "empty";
    }
    if (size >= 9 && data[0] == '2' && data[1] == 'D' && data[2] == 'A') {
        if (size >= 9 && data[4] == 'V' && data[5] == '2' && data[6] == '.' && data[7] == 'b' && data[8] == '\n') {
            return "binary_v2b";
        }
        if (size >= 7 && data[4] == 'V' && data[5] == '2' && data[6] == '.') {
            return "ascii_v2";
        }
    }
    return "unknown";
}

const char* twoda_cell_or_default(const char* value, const char* fallback) noexcept {
    static constexpr const char* kBlank = "****";
    const std::string text = value == nullptr ? std::string() : std::string(value);
    if (text.empty() || text == kBlank) {
        return fallback == nullptr ? "" : fallback;
    }
    thread_local std::string out;
    out = text;
    return out.c_str();
}

const char* split_twoda_line_json(const char* line) noexcept {
    thread_local std::string out;
    std::vector<std::string> tokens;
    std::string current;
    bool in_quote = false;
    const std::string text = line == nullptr ? std::string() : std::string(line);
    for (const char c : text) {
        if (c == '"') {
            in_quote = !in_quote;
        } else if ((c == ' ' || c == '\t') && !in_quote) {
            if (!current.empty()) {
                tokens.push_back(current == "****" ? std::string() : current);
                current.clear();
            }
        } else {
            current.push_back(c);
        }
    }
    if (!current.empty()) {
        tokens.push_back(current == "****" ? std::string() : current);
    }
    out = json_array(tokens);
    return out.c_str();
}

const char* templates_contracts_schema_json() noexcept {
    return R"({"schema":"templates_contracts_native.v1",)"
           R"("source":["src/core/templates/template_builder.py","src/core/templates/twoda.py"],)"
           R"("native_scope":["game-version normalization","humanoid template bone counts","humanoid template animation-slot counts","rig-source classification","2DA format detection","2DA blank-cell defaulting","ASCII 2DA line tokenization"],)"
           R"("python_fallback":["KotorModel construction","placeholder mesh construction","manifest file writes","PyKotor animation validation","eyeball node inspection","binary 2DA parsing","ASCII 2DA table parsing","2DA cache filesystem/GameLibrary access"],)"
           R"("reason_python_fallback":"Model construction, validation through PyKotor, table/file parsing, and cache access depend on runtime geometry objects, game files, or filesystem state that should be ported as dedicated validated slices"})";
}

} // namespace ghostrigger::core::templates::core::templates::contracts

extern "C" {

__declspec(dllexport) const char* gr_templates_normalize_game_version(const char* game_version) {
    return ghostrigger::core::templates::core::templates::contracts::normalize_game_version(game_version);
}

__declspec(dllexport) int gr_templates_humanoid_bone_count(const char* game_version) {
    return ghostrigger::core::templates::core::templates::contracts::humanoid_bone_count(game_version);
}

__declspec(dllexport) int gr_templates_humanoid_animation_slot_count(const char* game_version) {
    return ghostrigger::core::templates::core::templates::contracts::humanoid_animation_slot_count(game_version);
}

__declspec(dllexport) const char* gr_templates_humanoid_rig_source(const char* game_version) {
    return ghostrigger::core::templates::core::templates::contracts::humanoid_rig_source(game_version);
}

__declspec(dllexport) const char* gr_templates_detect_twoda_format(const unsigned char* data, unsigned int size) {
    return ghostrigger::core::templates::core::templates::contracts::detect_twoda_format(data, size);
}

__declspec(dllexport) const char* gr_templates_twoda_cell_or_default(const char* value, const char* fallback) {
    return ghostrigger::core::templates::core::templates::contracts::twoda_cell_or_default(value, fallback);
}

__declspec(dllexport) const char* gr_templates_split_twoda_line_json(const char* line) {
    return ghostrigger::core::templates::core::templates::contracts::split_twoda_line_json(line);
}

__declspec(dllexport) const char* gr_templates_contracts_schema_json() {
    return ghostrigger::core::templates::core::templates::contracts::templates_contracts_schema_json();
}

}
