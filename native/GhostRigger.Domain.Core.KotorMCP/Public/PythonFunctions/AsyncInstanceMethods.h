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

const NativeFunctionImplementation& fallbackhttpserver_handle_line_87_adab15d2_native();
const NativeFunctionImplementation& fallbackhttpserver_serve_line_162_44154bbb_native();

const NativeFunctionImplementation* asyncinstancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::kotormcp
