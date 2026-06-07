#pragma once

#include <cstddef>

namespace ghostrigger::native::nativecore::math {

#ifndef GHOSTRIGGER_NATIVE_NATIVECORE_MATH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_NATIVE_NATIVECORE_MATH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_NATIVE_NATIVECORE_MATH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& euler_degrees_to_quat_axis_quat_line_118_a2c38810_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::native::nativecore::math
