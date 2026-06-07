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

const char* src_gui_dialogs_qt_dialogs_show_about_line_384_8da757ad_descriptor_json();
const char* src_gui_dialogs_qt_dialogs_show_format_reference_line_396_c754379d_descriptor_json();
const char* src_gui_dialogs_qt_dialogs_show_viewport_navigation_reference_line_404_e88fda60_descriptor_json();
const char* src_gui_dialogs_qt_dialogs_show_ipc_info_line_412_046b12a9_descriptor_json();
const char* src_gui_dialogs_qt_settings_dialog_wgpu_backend_type_line_41_084a96fb_descriptor_json();
const char* src_gui_dialogs_qt_settings_dialog_load_settings_line_747_44c82cc7_descriptor_json();
const char* src_gui_dialogs_qt_settings_dialog_save_settings_line_756_1a1ccaf9_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_dialogs
