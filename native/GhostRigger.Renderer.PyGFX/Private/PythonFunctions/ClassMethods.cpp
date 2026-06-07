#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_renderer_pygfx {

const char* src_adapters_rendering_pygfx_core_renderer_pygfxviewportrenderer_probe_availability_line_87_bda39575_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.PyGFX","python_module":"src.adapters.rendering.pygfx_core.renderer","python_file":"src/adapters/rendering/pygfx_core/renderer.py","qualname":"PygfxViewportRenderer.probe_availability","name":"probe_availability","kind":"class_methods","line":87,"end_line":125,"signature":{"args":["cls"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_rendering_pygfx_core_scene_bridge_pygfxscenebridge_polyline_to_segments_line_524_5d05e78c_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.PyGFX","python_module":"src.adapters.rendering.pygfx_core.scene_bridge","python_file":"src/adapters/rendering/pygfx_core/scene_bridge.py","qualname":"PygfxSceneBridge._polyline_to_segments","name":"_polyline_to_segments","kind":"class_methods","line":524,"end_line":531,"signature":{"args":["cls","points"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/rendering/pygfx_core/renderer.py", "PygfxViewportRenderer.probe_availability", "class_methods", &src_adapters_rendering_pygfx_core_renderer_pygfxviewportrenderer_probe_availability_line_87_bda39575_descriptor_json},
        {"src/adapters/rendering/pygfx_core/scene_bridge.py", "PygfxSceneBridge._polyline_to_segments", "class_methods", &src_adapters_rendering_pygfx_core_scene_bridge_pygfxscenebridge_polyline_to_segments_line_524_5d05e78c_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_renderer_pygfx
