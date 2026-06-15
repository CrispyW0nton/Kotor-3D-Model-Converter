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

const NativeFunctionImplementation& build_mcp_server_list_tools_line_180_5a52d187_native();
const NativeFunctionImplementation& build_mcp_server_call_tool_line_192_0c31521b_native();
const NativeFunctionImplementation& build_mcp_server_list_res_line_198_cce3f6db_native();
const NativeFunctionImplementation& build_mcp_server_list_res_templates_line_211_bc6ea5bd_native();
const NativeFunctionImplementation& build_mcp_server_read_res_line_224_62c6234e_native();
const NativeFunctionImplementation& run_sse_app_line_253_968722ac_native();

const NativeFunctionImplementation* asyncnestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::kotormcp
