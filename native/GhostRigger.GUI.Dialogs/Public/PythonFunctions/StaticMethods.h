#pragma once

#include <cstddef>

namespace ghostrigger::gui::dialogs {

#ifndef GHOSTRIGGER_GUI_DIALOGS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_DIALOGS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_GUI_DIALOGS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& qtaboutdialog_window_icon_line_352_7eb68aaa_native();
const NativeFunctionImplementation& qtaboutdialog_renderer_status_line_363_4b84e3eb_native();
const NativeFunctionImplementation& qtaboutdialog_theme_status_line_373_40d02a86_native();
const NativeFunctionImplementation& qtsettingsdialog_coerce_hardware_diagnostics_line_422_9371990e_native();
const NativeFunctionImplementation& qtsettingsdialog_coerce_renderer_capabilities_line_430_3412f953_native();
const NativeFunctionImplementation& qtsettingsdialog_set_combo_data_line_551_9b7f556e_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::dialogs
