#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_modules {

const char* src_core_modules_module_editor_controller_moduleeditorcontroller_blueprint_type_for_library_asset_line_165_6428786f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Modules","python_module":"src.core.modules.module_editor_controller","python_file":"src/core/modules/module_editor_controller.py","qualname":"ModuleEditorController._blueprint_type_for_library_asset","name":"_blueprint_type_for_library_asset","kind":"static_methods","line":165,"end_line":178,"signature":{"args":["category","resref"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/modules/module_editor_controller.py", "ModuleEditorController._blueprint_type_for_library_asset", "static_methods", &src_core_modules_module_editor_controller_moduleeditorcontroller_blueprint_type_for_library_asset_line_165_6428786f_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_modules
