#pragma once

#include <cstddef>

namespace ghostrigger::runtime {

#ifndef GHOSTRIGGER_RUNTIME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RUNTIME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RUNTIME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& make_package_line_293_8ece9a00_native();
const NativeFunctionImplementation& register_alias_line_300_993b5427_native();
const NativeFunctionImplementation& register_group_line_310_731fa624_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::runtime
