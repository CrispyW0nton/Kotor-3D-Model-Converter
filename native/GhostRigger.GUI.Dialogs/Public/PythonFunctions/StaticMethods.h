#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_dialogs {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_dialogs_qt_dialogs_qtaboutdialog_window_icon_line_352_7eb68aaa_descriptor_json();
const char* src_gui_dialogs_qt_dialogs_qtaboutdialog_renderer_status_line_363_4b84e3eb_descriptor_json();
const char* src_gui_dialogs_qt_dialogs_qtaboutdialog_theme_status_line_373_40d02a86_descriptor_json();
const char* src_gui_dialogs_qt_settings_dialog_qtsettingsdialog_coerce_hardware_diagnostics_line_422_9371990e_descriptor_json();
const char* src_gui_dialogs_qt_settings_dialog_qtsettingsdialog_coerce_renderer_capabilities_line_430_3412f953_descriptor_json();
const char* src_gui_dialogs_qt_settings_dialog_qtsettingsdialog_set_combo_data_line_551_9b7f556e_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_dialogs
