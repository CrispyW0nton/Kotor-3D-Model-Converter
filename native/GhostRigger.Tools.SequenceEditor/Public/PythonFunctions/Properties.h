#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_sequenceeditor {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_sequence_sequence_binding_sequencebinding_missing_line_64_68724a08_descriptor_json();
const char* src_sequence_sequence_model_ghostriggerlevelsequence_duration_seconds_line_134_5192bc4a_descriptor_json();
const char* src_sequence_sequence_model_ghostriggerlevelsequence_time_line_138_79375b49_descriptor_json();
const char* src_sequence_sequence_track_sequencetrack_supports_duplicate_frames_line_48_14bff92f_descriptor_json();
const char* src_sequence_tracks_event_track_eventtrack_supports_duplicate_frames_line_18_87491932_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_sequenceeditor
