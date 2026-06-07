#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_tools_spritematerials {

const char* src_core_graphics_tex_atlas_texarraycache_hit_rate_line_113_9ddcc050_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SpriteMaterials","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"TexArrayCache.hit_rate","name":"hit_rate","kind":"properties","line":113,"end_line":115,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/graphics/tex_atlas.py", "TexArrayCache.hit_rate", "properties", &src_core_graphics_tex_atlas_texarraycache_hit_rate_line_113_9ddcc050_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_spritematerials
