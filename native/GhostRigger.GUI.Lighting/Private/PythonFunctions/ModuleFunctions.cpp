#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_gui_lighting {

const char* src_gui_lighting_init_getattr_line_23_8dc4fe30_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Lighting","python_module":"src.gui.lighting.__init__","python_file":"src/gui/lighting/__init__.py","qualname":"__getattr__","name":"__getattr__","kind":"module_functions","line":23,"end_line":29,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_gui_lighting_init_dir_line_32_48350e38_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Lighting","python_module":"src.gui.lighting.__init__","python_file":"src/gui/lighting/__init__.py","qualname":"__dir__","name":"__dir__","kind":"module_functions","line":32,"end_line":33,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/lighting/__init__.py", "__getattr__", "module_functions", &src_gui_lighting_init_getattr_line_23_8dc4fe30_descriptor_json},
        {"src/gui/lighting/__init__.py", "__dir__", "module_functions", &src_gui_lighting_init_dir_line_32_48350e38_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_lighting
