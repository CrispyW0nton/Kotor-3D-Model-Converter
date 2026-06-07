#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_tools_sequenceeditor {

const char* src_sequence_sequence_binding_sequencebinding_missing_line_64_68724a08_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SequenceEditor","python_module":"src.sequence.sequence_binding","python_file":"src/sequence/sequence_binding.py","qualname":"SequenceBinding.missing","name":"missing","kind":"properties","line":64,"end_line":65,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_sequence_sequence_model_ghostriggerlevelsequence_duration_seconds_line_134_5192bc4a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SequenceEditor","python_module":"src.sequence.sequence_model","python_file":"src/sequence/sequence_model.py","qualname":"GhostRiggerLevelSequence.duration_seconds","name":"duration_seconds","kind":"properties","line":134,"end_line":135,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_sequence_sequence_model_ghostriggerlevelsequence_time_line_138_79375b49_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SequenceEditor","python_module":"src.sequence.sequence_model","python_file":"src/sequence/sequence_model.py","qualname":"GhostRiggerLevelSequence.time","name":"time","kind":"properties","line":138,"end_line":139,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_sequence_sequence_track_sequencetrack_supports_duplicate_frames_line_48_14bff92f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SequenceEditor","python_module":"src.sequence.sequence_track","python_file":"src/sequence/sequence_track.py","qualname":"SequenceTrack.supports_duplicate_frames","name":"supports_duplicate_frames","kind":"properties","line":48,"end_line":49,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_sequence_tracks_event_track_eventtrack_supports_duplicate_frames_line_18_87491932_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SequenceEditor","python_module":"src.sequence.tracks.event_track","python_file":"src/sequence/tracks/event_track.py","qualname":"EventTrack.supports_duplicate_frames","name":"supports_duplicate_frames","kind":"properties","line":18,"end_line":19,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/sequence/sequence_binding.py", "SequenceBinding.missing", "properties", &src_sequence_sequence_binding_sequencebinding_missing_line_64_68724a08_descriptor_json},
        {"src/sequence/sequence_model.py", "GhostRiggerLevelSequence.duration_seconds", "properties", &src_sequence_sequence_model_ghostriggerlevelsequence_duration_seconds_line_134_5192bc4a_descriptor_json},
        {"src/sequence/sequence_model.py", "GhostRiggerLevelSequence.time", "properties", &src_sequence_sequence_model_ghostriggerlevelsequence_time_line_138_79375b49_descriptor_json},
        {"src/sequence/sequence_track.py", "SequenceTrack.supports_duplicate_frames", "properties", &src_sequence_sequence_track_sequencetrack_supports_duplicate_frames_line_48_14bff92f_descriptor_json},
        {"src/sequence/tracks/event_track.py", "EventTrack.supports_duplicate_frames", "properties", &src_sequence_tracks_event_track_eventtrack_supports_duplicate_frames_line_18_87491932_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_sequenceeditor
