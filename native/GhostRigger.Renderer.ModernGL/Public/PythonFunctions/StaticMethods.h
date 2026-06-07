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

const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_rgb_float_line_268_e7b708a6_descriptor_json();
const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_blend_rgb_line_272_744c4811_descriptor_json();
const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_relative_luma_line_277_03566a15_descriptor_json();
const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_light_kind_int_line_764_973329e8_descriptor_json();
const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_rotate_vec_by_quat_line_776_71b2a311_descriptor_json();
const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_sprite_text_line_2635_4ff16203_descriptor_json();
const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_has_sprite_material_override_line_2641_2bdcd1ae_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_moderngl
