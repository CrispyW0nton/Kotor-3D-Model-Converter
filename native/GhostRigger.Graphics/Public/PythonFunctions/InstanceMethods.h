#pragma once

#include <cstddef>

namespace ghostrigger::graphics {

#ifndef GHOSTRIGGER_GRAPHICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GRAPHICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GRAPHICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& texarraycache_construct_line_64_1c8a74d9_native();
const NativeFunctionImplementation& texarraycache_get_line_75_5ac63659_native();
const NativeFunctionImplementation& texarraycache_clear_line_105_bea9a5c0_native();
const NativeFunctionImplementation& texarraycache_len_line_109_543b7162_native();
const NativeFunctionImplementation& miparraycache_construct_line_143_312f6b9e_native();
const NativeFunctionImplementation& miparraycache_get_line_149_51bf3028_native();
const NativeFunctionImplementation& miparraycache_clear_line_169_a4460351_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::graphics
