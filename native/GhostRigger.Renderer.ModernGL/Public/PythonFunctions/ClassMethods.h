#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_moderngl {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_is_sprite_hilt_line_2650_5adc72a0_descriptor_json();
const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_sprite_alpha_source_line_2665_2b8129c9_descriptor_json();
const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_sprite_glow_line_2677_fe0a0901_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_moderngl
