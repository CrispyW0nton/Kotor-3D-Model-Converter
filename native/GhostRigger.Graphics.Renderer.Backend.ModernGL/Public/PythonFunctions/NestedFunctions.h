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

const NativeFunctionImplementation& gpurenderer_reset_framebuffers_release_fbo_line_504_5019d095_native();
const NativeFunctionImplementation& gpurenderer_draw_light_gizmos_add_line_line_637_feb19052_native();
const NativeFunctionImplementation& gpurenderer_draw_light_gizmos_v_add_line_641_e59255a2_native();
const NativeFunctionImplementation& gpurenderer_draw_light_gizmos_v_sub_line_642_47e39020_native();
const NativeFunctionImplementation& gpurenderer_draw_light_gizmos_v_mul_line_643_28d82d5e_native();
const NativeFunctionImplementation& gpurenderer_draw_light_gizmos_v_cross_line_644_062a2ffe_native();
const NativeFunctionImplementation& gpurenderer_draw_light_gizmos_v_norm_line_648_022e6be3_native();
const NativeFunctionImplementation& gpurenderer_draw_light_gizmos_basis_line_652_1b2b657d_native();
const NativeFunctionImplementation& gpurenderer_draw_light_gizmos_ring_line_659_bc45f374_native();
const NativeFunctionImplementation& gpurenderer_render_gpu_bas_attachment_root_for_node_line_1275_bb05e7ac_native();
const NativeFunctionImplementation& gpurenderer_render_gpu_bas_attachment_socket_node_line_1285_92df5627_native();
const NativeFunctionImplementation& gpurenderer_render_gpu_get_world_transform_line_1307_e9a27667_native();
const NativeFunctionImplementation& gpurenderer_render_gpu_is_deform_helper_line_1491_5fbfa3f7_native();
const NativeFunctionImplementation& gpurenderer_render_gpu_classify_node_line_1555_6979f6a4_native();
const NativeFunctionImplementation& gpurenderer_render_gpu_draw_node_line_1668_31be6fd4_native();
const NativeFunctionImplementation& gpurenderer_render_gpu_draw_node_multitex_line_2410_148a3c53_native();
const NativeFunctionImplementation& gpurenderer_render_gpu_node_sort_depth_line_2463_88d9337c_native();
const NativeFunctionImplementation& render_model_autoframe_axis_dist_line_72_357dc1a8_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::graphics::renderer::backend::moderngl
