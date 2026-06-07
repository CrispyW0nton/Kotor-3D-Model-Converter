#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::gui::sequenceeditor {

const NativeFunctionImplementation& sequenceeditorwindow_render_sequence_on_progress_line_846_12cb4eb8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.GUI.SequenceEditor",
        "ghostrigger::gui::sequenceeditor::sequence_editor::sequence_editor_window",
        "src/gui/sequence_editor/sequence_editor_window.py",
        "SequenceEditorWindow._render_sequence.on_progress",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.GUI.SequenceEditor","namespace":"ghostrigger::gui::sequenceeditor::sequence_editor::sequence_editor_window","python_file":"src/gui/sequence_editor/sequence_editor_window.py","qualname":"SequenceEditorWindow._render_sequence.on_progress","name":"on_progress","callable_type":"nested_functions","line":846,"end_line":851,"signature":{"args":["index","total","path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        sequenceeditorwindow_render_sequence_on_progress_line_846_12cb4eb8_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::gui::sequenceeditor
