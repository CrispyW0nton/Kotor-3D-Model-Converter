#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::phase15::ghostrigger_graphics {

const char* src_core_graphics_tex_atlas_texarraycache_init_line_64_1c8a74d9_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Graphics","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"TexArrayCache.__init__","name":"__init__","kind":"instance_methods","line":64,"end_line":71,"signature":{"args":["self","max_entries"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_graphics_tex_atlas_texarraycache_get_line_75_5ac63659_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Graphics","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"TexArrayCache.get","name":"get","kind":"instance_methods","line":75,"end_line":103,"signature":{"args":["self","img"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_graphics_tex_atlas_texarraycache_clear_line_105_bea9a5c0_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Graphics","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"TexArrayCache.clear","name":"clear","kind":"instance_methods","line":105,"end_line":107,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_graphics_tex_atlas_texarraycache_len_line_109_543b7162_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Graphics","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"TexArrayCache.__len__","name":"__len__","kind":"instance_methods","line":109,"end_line":110,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_graphics_tex_atlas_miparraycache_init_line_143_312f6b9e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Graphics","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"MipArrayCache.__init__","name":"__init__","kind":"instance_methods","line":143,"end_line":147,"signature":{"args":["self","max_entries"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_graphics_tex_atlas_miparraycache_get_line_149_51bf3028_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Graphics","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"MipArrayCache.get","name":"get","kind":"instance_methods","line":149,"end_line":167,"signature":{"args":["self","img"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_graphics_tex_atlas_miparraycache_clear_line_169_a4460351_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Graphics","python_module":"src.core.graphics.tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"MipArrayCache.clear","name":"clear","kind":"instance_methods","line":169,"end_line":170,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/graphics/tex_atlas.py", "TexArrayCache.__init__", "instance_methods", &src_core_graphics_tex_atlas_texarraycache_init_line_64_1c8a74d9_descriptor_json},
        {"src/core/graphics/tex_atlas.py", "TexArrayCache.get", "instance_methods", &src_core_graphics_tex_atlas_texarraycache_get_line_75_5ac63659_descriptor_json},
        {"src/core/graphics/tex_atlas.py", "TexArrayCache.clear", "instance_methods", &src_core_graphics_tex_atlas_texarraycache_clear_line_105_bea9a5c0_descriptor_json},
        {"src/core/graphics/tex_atlas.py", "TexArrayCache.__len__", "instance_methods", &src_core_graphics_tex_atlas_texarraycache_len_line_109_543b7162_descriptor_json},
        {"src/core/graphics/tex_atlas.py", "MipArrayCache.__init__", "instance_methods", &src_core_graphics_tex_atlas_miparraycache_init_line_143_312f6b9e_descriptor_json},
        {"src/core/graphics/tex_atlas.py", "MipArrayCache.get", "instance_methods", &src_core_graphics_tex_atlas_miparraycache_get_line_149_51bf3028_descriptor_json},
        {"src/core/graphics/tex_atlas.py", "MipArrayCache.clear", "instance_methods", &src_core_graphics_tex_atlas_miparraycache_clear_line_169_a4460351_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_graphics
