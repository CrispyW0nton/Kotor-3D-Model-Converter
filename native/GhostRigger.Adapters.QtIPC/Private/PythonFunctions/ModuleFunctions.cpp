#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::adapters::qtipc {

const NativeFunctionImplementation& marshal_to_gui_thread_line_9_545a70bd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.QtIPC",
        "ghostrigger::adapters::qtipc::qt_ipc::threading",
        "src/adapters/qt_ipc/threading.py",
        "marshal_to_gui_thread",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.QtIPC","namespace":"ghostrigger::adapters::qtipc::qt_ipc::threading","python_file":"src/adapters/qt_ipc/threading.py","qualname":"marshal_to_gui_thread","name":"marshal_to_gui_thread","callable_type":"module_functions","line":9,"end_line":20,"signature":{"args":["cb"],"positional_count":1,"keyword_only_count":0,"has_vararg":true,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        marshal_to_gui_thread_line_9_545a70bd_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::adapters::qtipc
