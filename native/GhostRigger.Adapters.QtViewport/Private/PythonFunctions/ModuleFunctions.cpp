#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_adapters_qtviewport {

const char* src_adapters_qt_viewport_frame_renderer_create_viewport_frame_renderer_line_6_3db885a3_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.QtViewport","python_module":"src.adapters.qt_viewport.frame_renderer","python_file":"src/adapters/qt_viewport/frame_renderer.py","qualname":"create_viewport_frame_renderer","name":"create_viewport_frame_renderer","kind":"module_functions","line":6,"end_line":10,"signature":{"args":["viewport"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_qt_viewport_frame_renderer_create_validation_frame_renderer_line_13_70d85031_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Adapters.QtViewport","python_module":"src.adapters.qt_viewport.frame_renderer","python_file":"src/adapters/qt_viewport/frame_renderer.py","qualname":"create_validation_frame_renderer","name":"create_validation_frame_renderer","kind":"module_functions","line":13,"end_line":24,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/qt_viewport/frame_renderer.py", "create_viewport_frame_renderer", "module_functions", &src_adapters_qt_viewport_frame_renderer_create_viewport_frame_renderer_line_6_3db885a3_descriptor_json},
        {"src/adapters/qt_viewport/frame_renderer.py", "create_validation_frame_renderer", "module_functions", &src_adapters_qt_viewport_frame_renderer_create_validation_frame_renderer_line_13_70d85031_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_adapters_qtviewport
