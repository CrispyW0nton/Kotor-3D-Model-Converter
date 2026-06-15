#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::validation {

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

const NativeFunctionImplementation& validate_raw_animation_footprint_walk_line_148_d39479ce_native();
const NativeFunctionImplementation& validationbus_subscribe_unsubscribe_line_158_b8f03986_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::validation
