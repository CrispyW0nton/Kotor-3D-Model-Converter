#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_adapters_qtautorig {

const char* src_adapters_qt_autorig_cloth_dialogs_qt_application_running_line_10_869101bf_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.QtAutorig","python_module":"src.adapters.qt_autorig.cloth_dialogs","python_file":"src/adapters/qt_autorig/cloth_dialogs.py","qualname":"_qt_application_running","name":"_qt_application_running","kind":"module_functions","line":10,"end_line":17,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_qt_autorig_cloth_dialogs_run_cloth_preset_dialog_line_20_6033aef6_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.QtAutorig","python_module":"src.adapters.qt_autorig.cloth_dialogs","python_file":"src/adapters/qt_autorig/cloth_dialogs.py","qualname":"run_cloth_preset_dialog","name":"run_cloth_preset_dialog","kind":"module_functions","line":20,"end_line":45,"signature":{"args":["parent","default_preset","title","message"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_qt_autorig_cloth_dialogs_confirm_cloth_action_line_48_c9074cd3_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.QtAutorig","python_module":"src.adapters.qt_autorig.cloth_dialogs","python_file":"src/adapters/qt_autorig/cloth_dialogs.py","qualname":"confirm_cloth_action","name":"confirm_cloth_action","kind":"module_functions","line":48,"end_line":69,"signature":{"args":["parent","title","message"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/qt_autorig/cloth_dialogs.py", "_qt_application_running", "module_functions", &src_adapters_qt_autorig_cloth_dialogs_qt_application_running_line_10_869101bf_descriptor_json},
        {"src/adapters/qt_autorig/cloth_dialogs.py", "run_cloth_preset_dialog", "module_functions", &src_adapters_qt_autorig_cloth_dialogs_run_cloth_preset_dialog_line_20_6033aef6_descriptor_json},
        {"src/adapters/qt_autorig/cloth_dialogs.py", "confirm_cloth_action", "module_functions", &src_adapters_qt_autorig_cloth_dialogs_confirm_cloth_action_line_48_c9074cd3_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_adapters_qtautorig
