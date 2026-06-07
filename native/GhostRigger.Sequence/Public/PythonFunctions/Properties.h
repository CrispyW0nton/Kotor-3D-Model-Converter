#pragma once

#include <cstddef>

namespace ghostrigger::sequence {

#ifndef GHOSTRIGGER_SEQUENCE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SEQUENCE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_SEQUENCE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& sequencebinding_missing_line_64_68724a08_native();
const NativeFunctionImplementation& ghostriggerlevelsequence_duration_seconds_line_134_5192bc4a_native();
const NativeFunctionImplementation& ghostriggerlevelsequence_time_line_138_79375b49_native();
const NativeFunctionImplementation& sequencetrack_supports_duplicate_frames_line_48_14bff92f_native();
const NativeFunctionImplementation& eventtrack_supports_duplicate_frames_line_18_87491932_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::sequence
