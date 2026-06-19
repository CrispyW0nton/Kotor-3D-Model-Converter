#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::gui::sequenceeditor {

const NativeFunctionImplementation& sequenceeditorwindow_split_track_spec_line_506_5d753815_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.SequenceEditor",
        "ghostrigger::core::gui::sequenceeditor::sequence_editor::sequence_editor_window",
        "src/gui/sequence_editor/sequence_editor_window.py",
        "SequenceEditorWindow._split_track_spec",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.SequenceEditor","namespace":"ghostrigger::core::gui::sequenceeditor::sequence_editor::sequence_editor_window","python_file":"src/gui/sequence_editor/sequence_editor_window.py","qualname":"SequenceEditorWindow._split_track_spec","name":"_split_track_spec","callable_type":"static_methods","line":506,"end_line":511,"signature":{"args":["track_type"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        sequenceeditorwindow_split_track_spec_line_506_5d753815_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::gui::sequenceeditor
