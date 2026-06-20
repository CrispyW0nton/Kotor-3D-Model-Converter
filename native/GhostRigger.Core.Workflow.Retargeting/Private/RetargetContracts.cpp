#include "RetargetContracts.h"

#include <cctype>
#include <string>

namespace ghostrigger::core::retargeting::core::retargeting::retarget_contracts {
namespace {

std::string strip_ascii_whitespace(std::string_view value) {
    std::size_t start = 0;
    std::size_t end = value.size();
    while (start < end && std::isspace(static_cast<unsigned char>(value[start]))) {
        ++start;
    }
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }
    return std::string(value.substr(start, end - start));
}

std::string lower_ascii(std::string_view value) {
    std::string result;
    result.reserve(value.size());
    for (const unsigned char character : value) {
        result.push_back(static_cast<char>(std::tolower(character)));
    }
    return result;
}

std::string upper_ascii(std::string_view value) {
    std::string result;
    result.reserve(value.size());
    for (const unsigned char character : value) {
        result.push_back(static_cast<char>(std::toupper(character)));
    }
    return result;
}

bool contains_forbidden_path_or_control_character(std::string_view text) noexcept {
    for (const unsigned char character : text) {
        if (character < 32 || character == '/' || character == '\\') {
            return true;
        }
    }
    return false;
}

} // namespace

RetargetMode coerce_retarget_mode(std::string_view value) noexcept {
    const std::string raw = strip_ascii_whitespace(value);
    if (raw.empty()) {
        return RetargetMode::Invalid;
    }
    const std::string lower = lower_ascii(raw);
    const std::string upper = upper_ascii(raw);
    if (raw == "kotor_to_kotor" || upper == "KOTOR_TO_KOTOR" || lower == "kotor \xe2\x86\x92 kotor") {
        return RetargetMode::KotorToKotor;
    }
    if (raw == "kotor_to_unreal" || upper == "KOTOR_TO_UNREAL" || lower == "kotor \xe2\x86\x92 unreal") {
        return RetargetMode::KotorToUnreal;
    }
    if (raw == "unreal_to_kotor" || upper == "UNREAL_TO_KOTOR" || lower == "unreal \xe2\x86\x92 kotor") {
        return RetargetMode::UnrealToKotor;
    }
    return RetargetMode::Invalid;
}

KotorOutputAnimationNameMode coerce_kotor_output_name_mode(std::string_view value) noexcept {
    const std::string raw = lower_ascii(strip_ascii_whitespace(value.empty() ? "vanilla_slot" : value));
    if (raw == "vanilla" || raw == "vanilla_slot" || raw == "slot") {
        return KotorOutputAnimationNameMode::VanillaSlot;
    }
    if (raw == "custom" || raw == "custom_patch" || raw == "patch") {
        return KotorOutputAnimationNameMode::CustomPatch;
    }
    return KotorOutputAnimationNameMode::Invalid;
}

bool is_kotor_output_mode(RetargetMode mode) noexcept {
    return mode == RetargetMode::KotorToKotor || mode == RetargetMode::UnrealToKotor;
}

bool is_kotor_output_mode(std::string_view mode) noexcept {
    return is_kotor_output_mode(coerce_retarget_mode(mode));
}

const char* retarget_mode_to_string(RetargetMode mode) noexcept {
    switch (mode) {
    case RetargetMode::KotorToKotor:
        return "kotor_to_kotor";
    case RetargetMode::KotorToUnreal:
        return "kotor_to_unreal";
    case RetargetMode::UnrealToKotor:
        return "unreal_to_kotor";
    case RetargetMode::Invalid:
    default:
        return "";
    }
}

const char* kotor_output_name_mode_to_string(KotorOutputAnimationNameMode mode) noexcept {
    switch (mode) {
    case KotorOutputAnimationNameMode::VanillaSlot:
        return "vanilla_slot";
    case KotorOutputAnimationNameMode::CustomPatch:
        return "custom_patch";
    case KotorOutputAnimationNameMode::Invalid:
    default:
        return "";
    }
}

const char* retarget_mode_specs_json() noexcept {
    static constexpr const char* kJson =
        R"([{"mode":"kotor_to_kotor","label":"KOTOR \u2192 KOTOR","source_kind":"kotor_aurora_model_animation_slot","target_kind":"kotor_aurora_model","output_kind":"kotor_mdl_mdx_animation_override","supports_preview":true,"supports_export":true,"implemented":true,"required_inputs":["source_kotor_model","source_kotor_animation_slot","target_model","retarget_profile","target_output_animation_name"]},)"
        R"({"mode":"kotor_to_unreal","label":"KOTOR \u2192 Unreal","source_kind":"kotor_aurora_model_animation_slot","target_kind":"unreal_skeleton","output_kind":"unreal_fbx_animation_clip","supports_preview":true,"supports_export":true,"implemented":true,"required_inputs":["source_kotor_model","source_kotor_animation_slot","target_unreal_skeleton","retarget_profile","output_unreal_clip_name"]},)"
        R"({"mode":"unreal_to_kotor","label":"Unreal \u2192 KOTOR","source_kind":"ue_fbx_source_clip","target_kind":"kotor_aurora_model","output_kind":"kotor_mdl_mdx_animation_override","supports_preview":true,"supports_export":true,"implemented":true,"required_inputs":["source_clip","target_model","retarget_profile"]}])";
    return kJson;
}

std::string validate_custom_kotor_animation_name(std::string_view name) {
    const std::string text = strip_ascii_whitespace(name);
    if (text.empty() || text == "." || text == ".." || text.size() > 64 || contains_forbidden_path_or_control_character(text)) {
        return {};
    }
    return text;
}

std::string sanitize_unreal_clip_name(std::string_view name) {
    const std::string text = strip_ascii_whitespace(name);
    std::string result;
    result.reserve(text.size());
    for (const unsigned char character : text) {
        const unsigned char value = character == ' ' ? '_' : character;
        if (std::isalnum(value) || value == '_' || value == '-') {
            result.push_back(static_cast<char>(value));
        }
    }
    while (!result.empty() && (result.front() == '_' || result.front() == '-')) {
        result.erase(result.begin());
    }
    while (!result.empty() && (result.back() == '_' || result.back() == '-')) {
        result.pop_back();
    }
    return result;
}

std::string validate_unreal_clip_name(std::string_view name) {
    const std::string text = strip_ascii_whitespace(name);
    if (text.empty() || text.size() > 128 || contains_forbidden_path_or_control_character(text)) {
        return {};
    }
    return sanitize_unreal_clip_name(text);
}

const char* retarget_contracts_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"retarget_contracts_native.v1",)"
        R"("sources":["src/core/retargeting/retarget_modes.py","src/core/retargeting/retarget_output_naming.py"],)"
        R"("native_scope":["RetargetMode coercion","RetargetModeSpec metadata","is_kotor_output_mode","KotorOutputAnimationNameMode coercion","custom KOTOR output name validation","Unreal clip name sanitization"],)"
        R"("python_fallback":["resolve_retarget_output_name vanilla slot resolution","animation slot lookup","target model and supermodel chain inspection","warning generation against resolved slots","retarget solver/export pipelines"],)"
        R"("reason_python_fallback":"full output-name resolution still depends on Python target model objects, animation slot services, and retarget/export runtime pipelines"})";
    return kJson;
}

} // namespace ghostrigger::core::retargeting::core::retargeting::retarget_contracts
