#include "QtAutorigContracts.h"

#include <array>
#include <string>
#include <string_view>
#include <vector>

// Win32 TaskDialogIndirect types require Windows SDK constants defined before including commctrl.
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0600
#endif
#include <windows.h>
#include <commctrl.h>

namespace ghostrigger::adapters::qtautorig {

namespace {

constexpr std::array<std::string_view, 11> kPresets = {
    "Revan's Cape (K1 reference)",
    "Revan's Belt (K1 reference)",
    "Jedi Robe (K1 standard)",
    "Robe (Loose / K2 default)",
    "Robe (Stiff / formal)",
    "Cape (Light)",
    "Cape (Heavy)",
    "Belt / Loin-cloth",
    "Skirt",
    "Sash / Scarf",
    "Stiff Collar",
};

constexpr const char* kChoiceSchema = "ghostrigger.adapters.qtautorig.cloth_preset_choice.v1";
constexpr int kTaskDialogPresetButtonBase = 1000;

std::wstring to_wide(std::string_view utf8) {
    if (utf8.empty()) {
        return {};
    }
    const int count = MultiByteToWideChar(CP_UTF8, 0, utf8.data(), static_cast<int>(utf8.size()), nullptr, 0);
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

std::size_t selected_preset_index(std::string_view default_preset) {
    if (default_preset.empty()) {
        return 0;
    }
    for (std::size_t idx = 0; idx < kPresets.size(); ++idx) {
        if (kPresets[idx] == default_preset) {
            return idx;
        }
    }
    return 0;
}

std::string format_choice_json(std::string_view preset_name, bool accepted, bool ui_available) {
    const std::string escaped_name = escape_json(preset_name);
    std::string json;
    json.reserve(256 + escaped_name.size() + kPresets.size() * 24);
    json += '{';
    json += "\"schema\":\"";
    json += kChoiceSchema;
    json += "\",\"preset_name\":\"";
    json += escaped_name;
    json += "\",\"accepted\":";
    json += accepted ? "true" : "false";
    json += ",\"ui_available\":";
    json += ui_available ? "true" : "false";
    json += ",\"available\":[";
    for (std::size_t i = 0; i < kPresets.size(); ++i) {
        if (i > 0) {
            json += ',';
        }
        json += '"';
        json += escape_json(kPresets[i]);
        json += '"';
    }
    json += ']';
    json += '}';
    return json;
}

using TaskDialogFn = HRESULT (WINAPI*)(const TASKDIALOGCONFIG*, int*, int*, BOOL*);

bool run_preset_task_dialog(
    const std::wstring& title_wide,
    const std::wstring& message_wide,
    std::size_t default_index,
    std::size_t& selected_index
) {
    HMODULE comctl = GetModuleHandleW(L"comctl32.dll");
    bool should_unload = false;
    if (comctl == nullptr) {
        comctl = LoadLibraryW(L"comctl32.dll");
        if (comctl == nullptr) {
            return false;
        }
        should_unload = true;
    }

    const auto* task_dialog = reinterpret_cast<TaskDialogFn>(GetProcAddress(comctl, "TaskDialogIndirect"));
    if (task_dialog == nullptr) {
        if (should_unload) {
            FreeLibrary(comctl);
        }
        return false;
    }

    std::vector<std::wstring> button_texts;
    button_texts.reserve(kPresets.size());
    std::vector<TASKDIALOG_BUTTON> buttons;
    buttons.reserve(kPresets.size());
    for (const auto& preset : kPresets) {
        button_texts.push_back(to_wide(preset));
        TASKDIALOG_BUTTON button {};
        button.nButtonID = kTaskDialogPresetButtonBase + static_cast<int>(button_texts.size() - 1);
        button.pszButtonText = button_texts.back().data();
        buttons.push_back(button);
    }

    TASKDIALOGCONFIG config{};
    config.cbSize = sizeof(config);
    config.hwndParent = nullptr;
    config.hInstance = nullptr;
    config.dwFlags = TDF_USE_COMMAND_LINKS | TDF_ALLOW_DIALOG_CANCELLATION;
    config.pszWindowTitle = title_wide.c_str();
    config.pszMainInstruction = message_wide.c_str();
    config.pszContent = L"Choose a cloth preset:";
    config.cButtons = static_cast<UINT>(buttons.size());
    config.pButtons = buttons.data();
    config.nDefaultButton = kTaskDialogPresetButtonBase + static_cast<int>(default_index);

    int selected_button_id = 0;
    HRESULT result = task_dialog(&config, &selected_button_id, nullptr, nullptr);
    if (should_unload) {
        FreeLibrary(comctl);
    }
    if (FAILED(result)) {
        return false;
    }
    if (selected_button_id < kTaskDialogPresetButtonBase ||
        selected_button_id >= kTaskDialogPresetButtonBase + static_cast<int>(kPresets.size())) {
        return false;
    }
    selected_index = static_cast<std::size_t>(selected_button_id - kTaskDialogPresetButtonBase);
    return true;
}

bool run_confirm_task_dialog(const std::wstring& title_wide, const std::wstring& message_wide) {
    HMODULE comctl = GetModuleHandleW(L"comctl32.dll");
    bool should_unload = false;
    if (comctl == nullptr) {
        comctl = LoadLibraryW(L"comctl32.dll");
        if (comctl == nullptr) {
            return true;
        }
        should_unload = true;
    }

    const auto* task_dialog = reinterpret_cast<TaskDialogFn>(GetProcAddress(comctl, "TaskDialogIndirect"));
    if (task_dialog == nullptr) {
        if (should_unload) {
            FreeLibrary(comctl);
        }
        return true;
    }

    TASKDIALOG_BUTTON buttons[] = {
        { IDYES, L"Yes" },
        { IDNO, L"No" },
    };

    TASKDIALOGCONFIG config{};
    config.cbSize = sizeof(config);
    config.hwndParent = nullptr;
    config.hInstance = nullptr;
    config.dwFlags = TDF_USE_COMMAND_LINKS | TDF_ALLOW_DIALOG_CANCELLATION;
    config.pszWindowTitle = title_wide.c_str();
    config.pszMainInstruction = message_wide.c_str();
    config.cButtons = 2;
    config.pButtons = buttons;
    config.nDefaultButton = IDYES;

    int selected_button_id = 0;
    HRESULT result = task_dialog(&config, &selected_button_id, nullptr, nullptr);
    if (should_unload) {
        FreeLibrary(comctl);
    }
    if (FAILED(result)) {
        return true;
    }
    return selected_button_id == IDYES;
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
        json = format_choice_json("", false, false);
        return json.c_str();
    }

    const std::string_view default_preset_text = default_preset == nullptr ? std::string_view{} : std::string_view(default_preset);
    std::size_t selected = selected_preset_index(default_preset_text);
    bool ui_available = qt_application_running();
    bool accepted = true;
    if (ui_available) {
        const std::string_view title_text = title == nullptr || title[0] == '\0'
            ? std::string_view("Cloth Rigging Preset")
            : std::string_view(title);
        const std::string_view message_text = message == nullptr || message[0] == '\0'
            ? std::string_view("Pick a cloth preset to apply to the selected node(s):")
            : std::string_view(message);
        const std::wstring title_wide = to_wide(title_text);
        const std::wstring message_wide = to_wide(message_text);
        std::size_t chosen_index = selected;
        if (!run_preset_task_dialog(title_wide, message_wide, selected, chosen_index)) {
            // Explicitly no-ui behavior: preserve prior choice and accept default to match phase-1 fallback rules.
            ui_available = false;
            accepted = true;
            chosen_index = selected;
        } else {
            selected = chosen_index;
            accepted = true;
        }
    } else {
        // Explicitly no-UI behavior when host Qt runtime is not available.
        ui_available = false;
        accepted = true;
    }

    json = format_choice_json(kPresets[selected], accepted, ui_available);
    return json.c_str();
}

bool confirm_cloth_action(const void*, const char* title, const char* message) {
    const bool qt_available = qt_application_running();
    if (!qt_available) {
        // Explicitly UI-unavailable fallback rule: default to true.
        return true;
    }

    const std::string_view title_text = title == nullptr || title[0] == '\0'
        ? std::string_view("Cloth Rigging")
        : std::string_view(title);
    const std::string_view message_text = message == nullptr || message[0] == '\0'
        ? std::string_view("Apply cloth rig to the selected node(s)?")
        : std::string_view(message);
    const std::wstring title_wide = to_wide(title_text);
    const std::wstring message_wide = to_wide(message_text);
    return run_confirm_task_dialog(title_wide, message_wide);
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
    (void)parent;
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
    (void)parent;
    return ghostrigger::adapters::qtautorig::confirm_cloth_action(parent, title, message) ? 1 : 0;
}

}
