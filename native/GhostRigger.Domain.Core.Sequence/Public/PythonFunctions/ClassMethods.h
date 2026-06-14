#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::sequence {

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

const NativeFunctionImplementation& sequencebinding_deserialize_line_93_e965cd49_native();
const NativeFunctionImplementation& sequencekeyframe_deserialize_line_54_58ea4257_native();
const NativeFunctionImplementation& sequencemarker_deserialize_line_79_3f88fc02_native();
const NativeFunctionImplementation& ghostriggerlevelsequence_deserialize_line_240_d646c358_native();
const NativeFunctionImplementation& sequencerendersettings_for_sequence_line_34_eb8a7514_native();
const NativeFunctionImplementation& sequencetrack_deserialize_line_132_ecf49285_native();
const NativeFunctionImplementation& sequencetrack_deserialize_base_line_146_c14f6cd4_native();
const NativeFunctionImplementation& audiotrack_deserialize_line_23_d8f97c48_native();
const NativeFunctionImplementation& cameracut_deserialize_line_35_6d88b350_native();
const NativeFunctionImplementation& cameracuttrack_deserialize_line_101_ace0bfd2_native();
const NativeFunctionImplementation& camerapropertytrack_deserialize_line_54_a03addfe_native();
const NativeFunctionImplementation& charactertrack_deserialize_line_24_92f07074_native();
const NativeFunctionImplementation& eventtrack_deserialize_line_65_cf26438d_native();
const NativeFunctionImplementation& lightpropertytrack_deserialize_line_55_71c8a198_native();
const NativeFunctionImplementation& materialtrack_deserialize_line_51_ed9b85b8_native();
const NativeFunctionImplementation& rigtrack_deserialize_line_24_1de00093_native();
const NativeFunctionImplementation& subsequencesection_deserialize_line_33_66c6838b_native();
const NativeFunctionImplementation& subsequencetrack_deserialize_line_67_904c0e07_native();
const NativeFunctionImplementation& transformpropertytrack_deserialize_line_66_1d6d4ca0_native();
const NativeFunctionImplementation& transformtrack_deserialize_line_47_12a7ff2b_native();
const NativeFunctionImplementation& visibilitytrack_deserialize_line_31_408a71b9_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::sequence
