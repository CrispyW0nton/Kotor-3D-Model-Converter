#pragma once

#include <cstddef>

namespace ghostrigger::core::animation {

#ifndef GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& animationretargeter_build_map_line_372_debf3019_native();
const NativeFunctionImplementation& animationretargeter_from_json_line_391_cc3025a4_native();
const NativeFunctionImplementation& animationretargeter_save_json_line_398_0daaa362_native();
const NativeFunctionImplementation& matrixpaletteuploader_qbone_inverse_bind_matrix_line_738_39b95042_native();
const NativeFunctionImplementation& matrixpaletteuploader_qbone_direct_bind_matrix_line_757_49040c9a_native();
const NativeFunctionImplementation& matrixpaletteuploader_qbone_inverse_bind_matrix_g5_line_779_8029ac58_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::animation
