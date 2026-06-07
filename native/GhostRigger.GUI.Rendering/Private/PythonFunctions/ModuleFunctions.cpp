#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_gui_rendering {

const char* src_gui_rendering_qt_gpu_renderer_getattr_line_18_624b26a0_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Rendering","python_module":"src.gui.rendering.qt_gpu_renderer","python_file":"src/gui/rendering/qt_gpu_renderer.py","qualname":"__getattr__","name":"__getattr__","kind":"module_functions","line":18,"end_line":25,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_gui_rendering_qt_gpu_renderer_dir_line_28_5ac68b36_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Rendering","python_module":"src.gui.rendering.qt_gpu_renderer","python_file":"src/gui/rendering/qt_gpu_renderer.py","qualname":"__dir__","name":"__dir__","kind":"module_functions","line":28,"end_line":29,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/rendering/qt_gpu_renderer.py", "__getattr__", "module_functions", &src_gui_rendering_qt_gpu_renderer_getattr_line_18_624b26a0_descriptor_json},
        {"src/gui/rendering/qt_gpu_renderer.py", "__dir__", "module_functions", &src_gui_rendering_qt_gpu_renderer_dir_line_28_5ac68b36_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_rendering
