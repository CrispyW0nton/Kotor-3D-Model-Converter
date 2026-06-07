#pragma once

#include <cstddef>

namespace ghostrigger::adapters::qtipc {

#ifndef GHOSTRIGGER_ADAPTERS_QTIPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ADAPTERS_QTIPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ADAPTERS_QTIPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& marshal_to_gui_thread_line_9_545a70bd_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::adapters::qtipc
