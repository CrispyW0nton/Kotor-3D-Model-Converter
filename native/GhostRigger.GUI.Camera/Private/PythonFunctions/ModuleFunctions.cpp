#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_gui_camera {

const char* src_gui_camera_init_getattr_line_19_bd15a5bb_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Camera","python_module":"src.gui.camera.__init__","python_file":"src/gui/camera/__init__.py","qualname":"__getattr__","name":"__getattr__","kind":"module_functions","line":19,"end_line":25,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_gui_camera_init_dir_line_28_8f929c2b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Camera","python_module":"src.gui.camera.__init__","python_file":"src/gui/camera/__init__.py","qualname":"__dir__","name":"__dir__","kind":"module_functions","line":28,"end_line":29,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/camera/__init__.py", "__getattr__", "module_functions", &src_gui_camera_init_getattr_line_19_bd15a5bb_descriptor_json},
        {"src/gui/camera/__init__.py", "__dir__", "module_functions", &src_gui_camera_init_dir_line_28_8f929c2b_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_camera
