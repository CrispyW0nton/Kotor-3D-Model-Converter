#pragma once

#include <cstddef>

namespace ghostrigger::core::infrastructure {

#ifndef GHOSTRIGGER_INFRA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_INFRA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_INFRA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& maybe_autostart_kotormcp_line_17_3a73802a_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::infrastructure
