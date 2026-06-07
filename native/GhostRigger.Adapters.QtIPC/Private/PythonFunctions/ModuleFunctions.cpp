#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_adapters_qtipc {

const char* src_adapters_qt_ipc_threading_marshal_to_gui_thread_line_9_545a70bd_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.QtIPC","python_module":"src.adapters.qt_ipc.threading","python_file":"src/adapters/qt_ipc/threading.py","qualname":"marshal_to_gui_thread","name":"marshal_to_gui_thread","kind":"module_functions","line":9,"end_line":20,"signature":{"args":["cb"],"positional_count":1,"keyword_only_count":0,"has_vararg":true,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/qt_ipc/threading.py", "marshal_to_gui_thread", "module_functions", &src_adapters_qt_ipc_threading_marshal_to_gui_thread_line_9_545a70bd_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_adapters_qtipc
