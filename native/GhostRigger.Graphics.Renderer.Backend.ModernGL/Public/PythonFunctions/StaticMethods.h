#pragma once

#include <cstddef>

namespace ghostrigger::graphics::renderer::backend::moderngl {

#ifndef GHOSTRIGGER_RENDERER_MODERNGL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RENDERER_MODERNGL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_RENDERER_MODERNGL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& gpurenderer_rgb_float_line_268_e7b708a6_native();
const NativeFunctionImplementation& gpurenderer_blend_rgb_line_272_744c4811_native();
const NativeFunctionImplementation& gpurenderer_relative_luma_line_277_03566a15_native();
const NativeFunctionImplementation& gpurenderer_light_kind_int_line_764_973329e8_native();
const NativeFunctionImplementation& gpurenderer_rotate_vec_by_quat_line_776_71b2a311_native();
const NativeFunctionImplementation& gpurenderer_sprite_text_line_2635_4ff16203_native();
const NativeFunctionImplementation& gpurenderer_has_sprite_material_override_line_2641_2bdcd1ae_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::graphics::renderer::backend::moderngl
