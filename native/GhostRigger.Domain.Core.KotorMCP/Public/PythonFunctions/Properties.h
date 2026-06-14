#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::kotormcp {

#ifndef GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& debugsession_uptime_s_line_119_caf797cb_native();
const NativeFunctionImplementation& resourceentryproxy_data_line_180_7da55bff_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::kotormcp
