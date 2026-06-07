#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_adapters_qtautorig {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_qt_autorig_cloth_dialogs_qt_application_running_line_10_869101bf_descriptor_json();
const char* src_adapters_qt_autorig_cloth_dialogs_run_cloth_preset_dialog_line_20_6033aef6_descriptor_json();
const char* src_adapters_qt_autorig_cloth_dialogs_confirm_cloth_action_line_48_c9074cd3_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_adapters_qtautorig
