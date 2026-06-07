#include "PythonFunctions/AsyncInstanceMethods.h"

namespace ghostrigger::kotormcp {

const NativeFunctionImplementation& fallbackhttpserver_handle_line_87_adab15d2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.KotorMCP",
        "ghostrigger::kotormcp::server",
        "src/kotormcp/server.py",
        "_FallbackHTTPServer.handle",
        "async_instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.KotorMCP","namespace":"ghostrigger::kotormcp::server","python_file":"src/kotormcp/server.py","qualname":"_FallbackHTTPServer.handle","name":"handle","callable_type":"async_instance_methods","line":87,"end_line":160,"signature":{"args":["self","reader","writer"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fallbackhttpserver_serve_line_162_44154bbb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.KotorMCP",
        "ghostrigger::kotormcp::server",
        "src/kotormcp/server.py",
        "_FallbackHTTPServer.serve",
        "async_instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.KotorMCP","namespace":"ghostrigger::kotormcp::server","python_file":"src/kotormcp/server.py","qualname":"_FallbackHTTPServer.serve","name":"serve","callable_type":"async_instance_methods","line":162,"end_line":170,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* asyncinstancemethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        fallbackhttpserver_handle_line_87_adab15d2_native(),
        fallbackhttpserver_serve_line_162_44154bbb_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::kotormcp
