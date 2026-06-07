#include "PythonFunctions/AsyncNestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_kotormcp {

const char* src_kotormcp_server_build_mcp_server_list_tools_line_180_5a52d187_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.server","python_file":"src/kotormcp/server.py","qualname":"_build_mcp_server.list_tools","name":"list_tools","kind":"async_nested_functions","line":180,"end_line":189,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_server_build_mcp_server_call_tool_line_192_0c31521b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.server","python_file":"src/kotormcp/server.py","qualname":"_build_mcp_server.call_tool","name":"call_tool","kind":"async_nested_functions","line":192,"end_line":195,"signature":{"args":["name","arguments"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_server_build_mcp_server_list_res_line_198_cce3f6db_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.server","python_file":"src/kotormcp/server.py","qualname":"_build_mcp_server.list_res","name":"list_res","kind":"async_nested_functions","line":198,"end_line":208,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_server_build_mcp_server_list_res_templates_line_211_bc6ea5bd_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.server","python_file":"src/kotormcp/server.py","qualname":"_build_mcp_server.list_res_templates","name":"list_res_templates","kind":"async_nested_functions","line":211,"end_line":221,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_server_build_mcp_server_read_res_line_224_62c6234e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.server","python_file":"src/kotormcp/server.py","qualname":"_build_mcp_server.read_res","name":"read_res","kind":"async_nested_functions","line":224,"end_line":225,"signature":{"args":["uri"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_server_run_sse_app_line_253_968722ac_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.server","python_file":"src/kotormcp/server.py","qualname":"_run_sse.app","name":"app","kind":"async_nested_functions","line":253,"end_line":263,"signature":{"args":["scope","receive","send"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* asyncnestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/kotormcp/server.py", "_build_mcp_server.list_tools", "async_nested_functions", &src_kotormcp_server_build_mcp_server_list_tools_line_180_5a52d187_descriptor_json},
        {"src/kotormcp/server.py", "_build_mcp_server.call_tool", "async_nested_functions", &src_kotormcp_server_build_mcp_server_call_tool_line_192_0c31521b_descriptor_json},
        {"src/kotormcp/server.py", "_build_mcp_server.list_res", "async_nested_functions", &src_kotormcp_server_build_mcp_server_list_res_line_198_cce3f6db_descriptor_json},
        {"src/kotormcp/server.py", "_build_mcp_server.list_res_templates", "async_nested_functions", &src_kotormcp_server_build_mcp_server_list_res_templates_line_211_bc6ea5bd_descriptor_json},
        {"src/kotormcp/server.py", "_build_mcp_server.read_res", "async_nested_functions", &src_kotormcp_server_build_mcp_server_read_res_line_224_62c6234e_descriptor_json},
        {"src/kotormcp/server.py", "_run_sse.app", "async_nested_functions", &src_kotormcp_server_run_sse_app_line_253_968722ac_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
