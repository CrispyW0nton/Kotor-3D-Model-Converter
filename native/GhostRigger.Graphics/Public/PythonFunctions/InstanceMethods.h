#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_graphics {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_graphics_tex_atlas_texarraycache_init_line_64_1c8a74d9_descriptor_json();
const char* src_core_graphics_tex_atlas_texarraycache_get_line_75_5ac63659_descriptor_json();
const char* src_core_graphics_tex_atlas_texarraycache_clear_line_105_bea9a5c0_descriptor_json();
const char* src_core_graphics_tex_atlas_texarraycache_len_line_109_543b7162_descriptor_json();
const char* src_core_graphics_tex_atlas_miparraycache_init_line_143_312f6b9e_descriptor_json();
const char* src_core_graphics_tex_atlas_miparraycache_get_line_149_51bf3028_descriptor_json();
const char* src_core_graphics_tex_atlas_miparraycache_clear_line_169_a4460351_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_graphics
