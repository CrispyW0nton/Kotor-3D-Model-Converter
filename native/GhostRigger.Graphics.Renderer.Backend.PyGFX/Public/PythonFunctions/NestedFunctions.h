#pragma once

#include <cstddef>

namespace ghostrigger::graphics::renderer::backend::pygfx {

#ifndef GHOSTRIGGER_RENDERER_PYGFX_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RENDERER_PYGFX_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RENDERER_PYGFX_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& pygfxmeshcache_build_geometric_boundary_edges_key_line_966_9d6153f3_native();
const NativeFunctionImplementation& wgpurenderer_create_gizmo_line_pipeline_create_pipeline_line_1086_a828ac49_native();
const NativeFunctionImplementation& wgpurenderer_draw_meshes_build_queue_line_1324_4c33a38f_native();
const NativeFunctionImplementation& wgpurenderer_draw_meshes_draw_pass_line_1420_012d61e7_native();
const NativeFunctionImplementation& wgpurenderer_mesh_model_matrix_stored_world_matrix_line_1576_96b0e67d_native();
const NativeFunctionImplementation& wgpurenderer_ensure_light_resource_score_line_1774_8290fbca_native();
const NativeFunctionImplementation& wgpurenderer_draw_light_overlays_draw_batches_line_1913_228e0eb1_native();
const NativeFunctionImplementation& wgpurenderer_draw_skeleton_overlay_draw_buffer_line_2042_17a991c9_native();
const NativeFunctionImplementation& wgpurenderer_get_or_upload_skeleton_resource_make_buffer_line_2092_22813374_native();
const NativeFunctionImplementation& wgpuresourcecache_build_geometric_boundary_edges_key_line_275_e4f6976e_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::graphics::renderer::backend::pygfx
