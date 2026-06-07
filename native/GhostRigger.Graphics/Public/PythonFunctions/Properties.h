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

const char* src_core_graphics_tex_atlas_texarraycache_hit_rate_line_113_9ddcc050_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_graphics
