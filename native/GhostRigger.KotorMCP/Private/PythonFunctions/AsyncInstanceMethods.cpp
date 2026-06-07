#include "PythonFunctions/AsyncInstanceMethods.h"

namespace ghostrigger::phase15::ghostrigger_kotormcp {

const char* src_kotormcp_server_fallbackhttpserver_handle_line_87_adab15d2_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.server","python_file":"src/kotormcp/server.py","qualname":"_FallbackHTTPServer.handle","name":"handle","kind":"async_instance_methods","line":87,"end_line":160,"signature":{"args":["self","reader","writer"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_server_fallbackhttpserver_serve_line_162_44154bbb_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.server","python_file":"src/kotormcp/server.py","qualname":"_FallbackHTTPServer.serve","name":"serve","kind":"async_instance_methods","line":162,"end_line":170,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* asyncinstancemethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/kotormcp/server.py", "_FallbackHTTPServer.handle", "async_instance_methods", &src_kotormcp_server_fallbackhttpserver_handle_line_87_adab15d2_descriptor_json},
        {"src/kotormcp/server.py", "_FallbackHTTPServer.serve", "async_instance_methods", &src_kotormcp_server_fallbackhttpserver_serve_line_162_44154bbb_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
