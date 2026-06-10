#include "QtAutorigContracts.h"

#include <array>
#include <string>
#include <string_view>

#include <windows.h>

namespace ghostrigger::adapters::qtautorig {

namespace {

constexpr std::array<const char*, 4> kPresets = {
    "Robe (Loose / K2 default)",
    "Cape (Light)",
    "Cape (Heavy)",
    "Belt / Loin-cloth",
};

const char* schema_json() {
    static constexpr const char* value = "ghostrigger.adapters.qtautorig.cloth_dialog_choice.v1";
    return value;
}

std::wstring to_wide(std::string_view utf8) {
    if (utf8.empty()) {
        return {};
    }
    const int count = MultiByteToWideChar(
        CP_UTF8,
        0,
        utf8.data(),
        static_cast<int>(utf8.size()),
        nullptr,
        0
    );
    if (count <= 0) {
        return {};
    }
    std::wstring out;
    out.resize(static_cast<std::size_t>(count));
    MultiByteToWideChar(CP_UTF8, 0, utf8.data(), static_cast<int>(utf8.size()), out.data(), count);
    return out;
}

std::string escape_json(std::string_view value) {
    std::string output;
    output.reserve(value.size() + 8);
    for (const char ch : value) {
        switch (ch) {
        case '\\':
            output += "\\\\";
            break;
        case '"':
            output += "\\\"";
            break;
        case '\n':
            output += "\\n";
            break;
        case '\r':
            output += "\\r";
            break;
        case '\t':
            output += "\\t";
            break;
        default:
            output += ch;
            break;
        }
    }
    return output;
}

const char* selected_preset(std::string_view default_preset) {
    if (kPresets.empty()) {
        return "";
    }
    if (!default_preset.empty()) {
        for (const char* preset : kPresets) {
            if (std::string_view(preset) == default_preset) {
                return preset;
            }
        }
    }
    return kPresets[0];
}

std::string format_choice_json(std::string_view preset_name, bool accepted) {
    const std::string escaped = escape_json(preset_name);
    std::string json;
    json.reserve(96 + escaped.size());
    json += '{';
    json += "\"schema\":\"";
    json += schema_json();
    json += "\",\"preset_name\":\"";
    json += escaped;
    json += "\",\"accepted\":";
    json += accepted ? "true" : "false";
    json += '}';
    return json;
}

} // namespace

bool qt_application_running() {
    return GetModuleHandleW(L"Qt6Core.dll") != nullptr || GetModuleHandleW(L"Qt5Core.dll") != nullptr;
}

const char* run_cloth_preset_dialog(
    const void*,
    const char* default_preset,
    const char* title,
    const char* message
) {
    static thread_local std::string json;

    if (kPresets.empty()) {
        json = format_choice_json("", false);
        return json.c_str();
    }

    const char* selected = selected_preset(default_preset == nullptr ? std::string_view{} : std::string_view(default_preset));
    if (!qt_application_running()) {
        json = format_choice_json(selected, true);
        return json.c_str();
    }

    const std::string_view title_text = (title == nullptr || title[0] == '\0')
        ? std::string_view("Cloth Preset")
        : std::string_view(title);
    const std::string_view message_text = (message == nullptr || message[0] == '\0')
        ? std::string_view("Use the selected cloth preset?")
        : std::string_view(message);
    const std::wstring message_wide = to_wide(message_text);
    const std::wstring title_wide = to_wide(title_text);

    const int response = MessageBoxW(
        nullptr,
        message_wide.c_str(),
        title_wide.c_str(),
        MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
    );
    json = format_choice_json(selected, response == IDYES);
    return json.c_str();
}

bool confirm_cloth_action(const void*, const char* title, const char* message) {
    if (!qt_application_running()) {
        return true;
    }
    const std::string_view title_text = (title == nullptr || title[0] == '\0')
        ? std::string_view("Cloth Rigging")
        : std::string_view(title);
    const std::string_view message_text = (message == nullptr || message[0] == '\0')
        ? std::string_view("Apply cloth rig to the selected node(s)?")
        : std::string_view(message);
    const std::wstring title_wide = to_wide(title_text);
    const std::wstring message_wide = to_wide(message_text);
    const int response = MessageBoxW(
        nullptr,
        message_wide.c_str(),
        title_wide.c_str(),
        MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
    );
    return response == IDYES;
}

} // namespace ghostrigger::adapters::qtautorig

extern "C" {

GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API int gr_adapters_qt_autorig_qt_application_running() {
    return ghostrigger::adapters::qtautorig::qt_application_running() ? 1 : 0;
}

GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_run_cloth_preset_dialog(
    const void* parent,
    const char* default_preset,
    const char* title,
    const char* message
) {
    return ghostrigger::adapters::qtautorig::run_cloth_preset_dialog(
        parent,
        default_preset,
        title,
        message
    );
}

GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API int gr_adapters_qt_autorig_confirm_cloth_action(
    const void* parent,
    const char* title,
    const char* message
) {
    return ghostrigger::adapters::qtautorig::confirm_cloth_action(parent, title, message) ? 1 : 0;
}

}
