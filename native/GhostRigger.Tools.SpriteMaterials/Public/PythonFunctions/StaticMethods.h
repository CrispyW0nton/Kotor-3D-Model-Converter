#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_spritematerials {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_graphics_tex_atlas_texarraycache_convert_line_120_742e16bf_descriptor_json();
const char* src_core_graphics_tex_atlas_miparraycache_convert_mip1_line_173_22a0ae15_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_spritematerials
