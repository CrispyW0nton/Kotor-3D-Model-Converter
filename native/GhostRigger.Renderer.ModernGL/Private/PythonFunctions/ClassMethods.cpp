#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_renderer_moderngl {

const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_is_sprite_hilt_line_2650_5adc72a0_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.ModernGL","python_module":"src.adapters.rendering.moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer._is_sprite_hilt","name":"_is_sprite_hilt","kind":"class_methods","line":2650,"end_line":2662,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_sprite_alpha_source_line_2665_2b8129c9_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.ModernGL","python_module":"src.adapters.rendering.moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer._sprite_alpha_source","name":"_sprite_alpha_source","kind":"class_methods","line":2665,"end_line":2674,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_sprite_glow_line_2677_fe0a0901_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.ModernGL","python_module":"src.adapters.rendering.moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer._sprite_glow","name":"_sprite_glow","kind":"class_methods","line":2677,"end_line":2687,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/rendering/moderngl_renderer_impl.py", "GpuRenderer._is_sprite_hilt", "class_methods", &src_adapters_rendering_moderngl_renderer_impl_gpurenderer_is_sprite_hilt_line_2650_5adc72a0_descriptor_json},
        {"src/adapters/rendering/moderngl_renderer_impl.py", "GpuRenderer._sprite_alpha_source", "class_methods", &src_adapters_rendering_moderngl_renderer_impl_gpurenderer_sprite_alpha_source_line_2665_2b8129c9_descriptor_json},
        {"src/adapters/rendering/moderngl_renderer_impl.py", "GpuRenderer._sprite_glow", "class_methods", &src_adapters_rendering_moderngl_renderer_impl_gpurenderer_sprite_glow_line_2677_fe0a0901_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_renderer_moderngl
