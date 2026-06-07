#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_kotormcp {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_kotormcp_server_build_mcp_server_list_tools_line_180_5a52d187_descriptor_json();
const char* src_kotormcp_server_build_mcp_server_call_tool_line_192_0c31521b_descriptor_json();
const char* src_kotormcp_server_build_mcp_server_list_res_line_198_cce3f6db_descriptor_json();
const char* src_kotormcp_server_build_mcp_server_list_res_templates_line_211_bc6ea5bd_descriptor_json();
const char* src_kotormcp_server_build_mcp_server_read_res_line_224_62c6234e_descriptor_json();
const char* src_kotormcp_server_run_sse_app_line_253_968722ac_descriptor_json();

const PythonFunctionDescriptorEntry* asyncnestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
