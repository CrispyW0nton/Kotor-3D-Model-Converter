#include "PythonFunctions/Properties.h"

namespace ghostrigger::core::ipc {

const NativeFunctionImplementation& ghostriggeripcserver_is_running_line_86_e9c58b6b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.IPC",
        "ghostrigger::core::ipc::server",
        "src/ipc/server.py",
        "GhostRiggerIPCServer.is_running",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.IPC","namespace":"ghostrigger::core::ipc::server","python_file":"src/ipc/server.py","qualname":"GhostRiggerIPCServer.is_running","name":"is_running","callable_type":"properties","line":86,"end_line":87,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        ghostriggeripcserver_is_running_line_86_e9c58b6b_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::ipc
