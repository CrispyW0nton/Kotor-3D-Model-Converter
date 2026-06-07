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

const char* src_gui_dialogs_add_model_to_scene_dialog_addmodeltoscenedialog_remember_choice_line_81_fd2c0ca3_descriptor_json();
const char* src_gui_dialogs_add_model_to_scene_dialog_addmodeltoscenedialog_placement_mode_line_85_6874109e_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_dialogs
