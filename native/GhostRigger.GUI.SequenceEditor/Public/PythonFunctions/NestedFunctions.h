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

const char* src_gui_sequence_editor_sequence_editor_window_sequenceeditorwindow_render_sequence_on_progress_line_846_12cb4eb8_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_sequenceeditor
