#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_ipc {

const char* src_ipc_server_ghostriggeripcserver_is_running_line_86_e9c58b6b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.IPC","python_module":"src.ipc.server","python_file":"src/ipc/server.py","qualname":"GhostRiggerIPCServer.is_running","name":"is_running","kind":"properties","line":86,"end_line":87,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/ipc/server.py", "GhostRiggerIPCServer.is_running", "properties", &src_ipc_server_ghostriggeripcserver_is_running_line_86_e9c58b6b_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_ipc
