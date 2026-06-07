#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_sequenceeditor {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_sequence_editor_sequence_editor_window_sequenceeditorwindow_split_track_spec_line_506_5d753815_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_sequenceeditor
