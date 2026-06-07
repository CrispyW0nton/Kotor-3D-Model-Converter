#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_spritematerials {

const char* src_core_graphics_tex_atlas_texarraycache_convert_line_120_742e16bf_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SpriteMaterials","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"TexArrayCache._convert","name":"_convert","kind":"static_methods","line":120,"end_line":129,"signature":{"args":["img"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_graphics_tex_atlas_miparraycache_convert_mip1_line_173_22a0ae15_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.SpriteMaterials","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"MipArrayCache._convert_mip1","name":"_convert_mip1","kind":"static_methods","line":173,"end_line":186,"signature":{"args":["img"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/graphics/tex_atlas.py", "TexArrayCache._convert", "static_methods", &src_core_graphics_tex_atlas_texarraycache_convert_line_120_742e16bf_descriptor_json},
        {"src/core/graphics/tex_atlas.py", "MipArrayCache._convert_mip1", "static_methods", &src_core_graphics_tex_atlas_miparraycache_convert_mip1_line_173_22a0ae15_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_spritematerials
