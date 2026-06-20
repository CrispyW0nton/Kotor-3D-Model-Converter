#pragma once

#include <cstddef>

namespace ghostrigger::core::ipc {

#ifndef GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_IPC_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& ghostriggeripcserver_is_running_line_86_e9c58b6b_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::ipc
