#pragma once

#include <cstddef>

namespace ghostrigger::adapters::scripting {

#ifndef GHOSTRIGGER_ADAPTERS_SCRIPTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ADAPTERS_SCRIPTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ADAPTERS_SCRIPTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& unavailablescriptcompiler_compile_script_line_29_00747c15_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::adapters::scripting
