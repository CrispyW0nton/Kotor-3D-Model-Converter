#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_gui_sequenceeditor {

const char* src_gui_sequence_editor_sequence_editor_window_sequenceeditorwindow_split_track_spec_line_506_5d753815_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.SequenceEditor","python_module":"src.gui.sequence_editor.sequence_editor_window","python_file":"src/gui/sequence_editor/sequence_editor_window.py","qualname":"SequenceEditorWindow._split_track_spec","name":"_split_track_spec","kind":"static_methods","line":506,"end_line":511,"signature":{"args":["track_type"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/sequence_editor/sequence_editor_window.py", "SequenceEditorWindow._split_track_spec", "static_methods", &src_gui_sequence_editor_sequence_editor_window_sequenceeditorwindow_split_track_spec_line_506_5d753815_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_sequenceeditor
