#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_camera {

const char* src_core_camera_render_manifest_append_render_manifest_line_24_1e0aa46a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Camera","python_module":"src.core.camera.render_manifest","python_file":"src/core/camera/render_manifest.py","qualname":"append_render_manifest","name":"append_render_manifest","kind":"module_functions","line":24,"end_line":37,"signature":{"args":["output_directory","entry"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/camera/render_manifest.py", "append_render_manifest", "module_functions", &src_core_camera_render_manifest_append_render_manifest_line_24_1e0aa46a_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_camera
