#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_windows_leveleditor {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_windows_module_editor_window_moduleeditorwindow_project_line_64_2e88ed80_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_windows_leveleditor
