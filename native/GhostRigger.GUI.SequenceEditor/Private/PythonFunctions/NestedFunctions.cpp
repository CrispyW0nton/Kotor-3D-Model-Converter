#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_gui_sequenceeditor {

const char* src_gui_sequence_editor_sequence_editor_window_sequenceeditorwindow_render_sequence_on_progress_line_846_12cb4eb8_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.SequenceEditor","python_module":"src.gui.sequence_editor.sequence_editor_window","python_file":"src/gui/sequence_editor/sequence_editor_window.py","qualname":"SequenceEditorWindow._render_sequence.on_progress","name":"on_progress","kind":"nested_functions","line":846,"end_line":851,"signature":{"args":["index","total","path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/sequence_editor/sequence_editor_window.py", "SequenceEditorWindow._render_sequence.on_progress", "nested_functions", &src_gui_sequence_editor_sequence_editor_window_sequenceeditorwindow_render_sequence_on_progress_line_846_12cb4eb8_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_sequenceeditor
