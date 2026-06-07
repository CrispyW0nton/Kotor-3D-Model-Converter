#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_runtime {

const char* src_core_qt_core_make_package_line_293_8ece9a00_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime","python_module":"src.core.qt_core","python_file":"src/core/qt_core.py","qualname":"_make_package","name":"_make_package","kind":"module_functions","line":293,"end_line":297,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_qt_core_register_alias_line_300_993b5427_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime","python_module":"src.core.qt_core","python_file":"src/core/qt_core.py","qualname":"_register_alias","name":"_register_alias","kind":"module_functions","line":300,"end_line":307,"signature":{"args":["alias","target"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_qt_core_register_group_line_310_731fa624_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime","python_module":"src.core.qt_core","python_file":"src/core/qt_core.py","qualname":"_register_group","name":"_register_group","kind":"module_functions","line":310,"end_line":324,"signature":{"args":["group","modules"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/qt_core.py", "_make_package", "module_functions", &src_core_qt_core_make_package_line_293_8ece9a00_descriptor_json},
        {"src/core/qt_core.py", "_register_alias", "module_functions", &src_core_qt_core_register_alias_line_300_993b5427_descriptor_json},
        {"src/core/qt_core.py", "_register_group", "module_functions", &src_core_qt_core_register_group_line_310_731fa624_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_runtime
