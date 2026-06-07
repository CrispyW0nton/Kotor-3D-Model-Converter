#pragma once

#include <cstddef>

namespace ghostrigger::validation {

#ifndef GHOSTRIGGER_VALIDATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_VALIDATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_VALIDATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& viewportvalidator_looks_like_ascii_mdl_line_58_29f4113d_native();
const NativeFunctionImplementation& viewportvalidator_game_version_line_72_8a0a958f_native();
const NativeFunctionImplementation& viewportvalidator_to_wxyz_line_245_84c4d9fa_native();
const NativeFunctionImplementation& viewportvalidator_read_grayscale_line_283_29fcf5e8_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::validation
