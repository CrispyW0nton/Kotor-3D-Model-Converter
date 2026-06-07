#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_renderer_moderngl {

const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_is_gpu_line_2716_996d44b7_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.ModernGL","python_module":"src.adapters.rendering.moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer.is_gpu","name":"is_gpu","kind":"properties","line":2716,"end_line":2718,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/rendering/moderngl_renderer_impl.py", "GpuRenderer.is_gpu", "properties", &src_adapters_rendering_moderngl_renderer_impl_gpurenderer_is_gpu_line_2716_996d44b7_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_renderer_moderngl
