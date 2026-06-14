#include "PythonFunctions/Properties.h"

namespace ghostrigger::tools::workflow::sequenceeditor {

const NativeFunctionImplementation& sequencebinding_missing_line_64_68724a08_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SequenceEditor",
        "ghostrigger::tools::workflow::sequenceeditor::sequence::sequence_binding",
        "src/sequence/sequence_binding.py",
        "SequenceBinding.missing",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SequenceEditor","namespace":"ghostrigger::tools::workflow::sequenceeditor::sequence::sequence_binding","python_file":"src/sequence/sequence_binding.py","qualname":"SequenceBinding.missing","name":"missing","callable_type":"properties","line":64,"end_line":65,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& ghostriggerlevelsequence_duration_seconds_line_134_5192bc4a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SequenceEditor",
        "ghostrigger::tools::workflow::sequenceeditor::sequence::sequence_model",
        "src/sequence/sequence_model.py",
        "GhostRiggerLevelSequence.duration_seconds",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SequenceEditor","namespace":"ghostrigger::tools::workflow::sequenceeditor::sequence::sequence_model","python_file":"src/sequence/sequence_model.py","qualname":"GhostRiggerLevelSequence.duration_seconds","name":"duration_seconds","callable_type":"properties","line":134,"end_line":135,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& ghostriggerlevelsequence_time_line_138_79375b49_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SequenceEditor",
        "ghostrigger::tools::workflow::sequenceeditor::sequence::sequence_model",
        "src/sequence/sequence_model.py",
        "GhostRiggerLevelSequence.time",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SequenceEditor","namespace":"ghostrigger::tools::workflow::sequenceeditor::sequence::sequence_model","python_file":"src/sequence/sequence_model.py","qualname":"GhostRiggerLevelSequence.time","name":"time","callable_type":"properties","line":138,"end_line":139,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& sequencetrack_supports_duplicate_frames_line_48_14bff92f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SequenceEditor",
        "ghostrigger::tools::workflow::sequenceeditor::sequence::sequence_track",
        "src/sequence/sequence_track.py",
        "SequenceTrack.supports_duplicate_frames",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SequenceEditor","namespace":"ghostrigger::tools::workflow::sequenceeditor::sequence::sequence_track","python_file":"src/sequence/sequence_track.py","qualname":"SequenceTrack.supports_duplicate_frames","name":"supports_duplicate_frames","callable_type":"properties","line":48,"end_line":49,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& eventtrack_supports_duplicate_frames_line_18_87491932_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.SequenceEditor",
        "ghostrigger::tools::workflow::sequenceeditor::sequence::tracks::event_track",
        "src/sequence/tracks/event_track.py",
        "EventTrack.supports_duplicate_frames",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.SequenceEditor","namespace":"ghostrigger::tools::workflow::sequenceeditor::sequence::tracks::event_track","python_file":"src/sequence/tracks/event_track.py","qualname":"EventTrack.supports_duplicate_frames","name":"supports_duplicate_frames","callable_type":"properties","line":18,"end_line":19,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        sequencebinding_missing_line_64_68724a08_native(),
        ghostriggerlevelsequence_duration_seconds_line_134_5192bc4a_native(),
        ghostriggerlevelsequence_time_line_138_79375b49_native(),
        sequencetrack_supports_duplicate_frames_line_48_14bff92f_native(),
        eventtrack_supports_duplicate_frames_line_18_87491932_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::workflow::sequenceeditor
