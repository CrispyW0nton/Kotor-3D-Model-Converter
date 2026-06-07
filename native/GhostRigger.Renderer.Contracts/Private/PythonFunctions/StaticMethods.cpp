#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_renderer_contracts {

const char* src_core_rendering_renderer_settings_renderersettings_apply_defaults_line_152_cad434f7_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.Contracts","python_module":"src.core.rendering.renderer_settings","python_file":"src/core/rendering/renderer_settings.py","qualname":"RendererSettings.apply_defaults","name":"apply_defaults","kind":"static_methods","line":152,"end_line":167,"signature":{"args":["settings"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/rendering/renderer_settings.py", "RendererSettings.apply_defaults", "static_methods", &src_core_rendering_renderer_settings_renderersettings_apply_defaults_line_152_cad434f7_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_renderer_contracts
