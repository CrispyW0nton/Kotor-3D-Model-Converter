#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_renderer_d3d12 {

const char* src_core_rendering_gpu_diagnostics_records_texture_content_stats_sample_line_180_6862de25_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.D3D12","python_module":"src.core.rendering.gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_texture_content_stats._sample","name":"_sample","kind":"nested_functions","line":180,"end_line":187,"signature":{"args":["x0","y0"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_rendering_gpu_diagnostics_records_skin_3g_candidate_records_norm_pos_line_1096_04f54701_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.D3D12","python_module":"src.core.rendering.gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_3g_candidate_records._norm_pos","name":"_norm_pos","kind":"nested_functions","line":1096,"end_line":1103,"signature":{"args":["acc"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_rendering_gpu_diagnostics_records_skin_3g_candidate_records_delta_to_production_line_1109_482a84f4_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.D3D12","python_module":"src.core.rendering.gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_3g_candidate_records._delta_to_production","name":"_delta_to_production","kind":"nested_functions","line":1109,"end_line":1115,"signature":{"args":["pos"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_rendering_gpu_scene_helpers_compositemodel_init_bb_line_204_ce6728e6_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Renderer.D3D12","python_module":"src.core.rendering.gpu_scene_helpers","python_file":"src/core/rendering/gpu_scene_helpers.py","qualname":"_CompositeModel.__init__._bb","name":"_bb","kind":"nested_functions","line":204,"end_line":206,"signature":{"args":["m","attr","default"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/rendering/gpu_diagnostics_records.py", "_texture_content_stats._sample", "nested_functions", &src_core_rendering_gpu_diagnostics_records_texture_content_stats_sample_line_180_6862de25_descriptor_json},
        {"src/core/rendering/gpu_diagnostics_records.py", "_skin_3g_candidate_records._norm_pos", "nested_functions", &src_core_rendering_gpu_diagnostics_records_skin_3g_candidate_records_norm_pos_line_1096_04f54701_descriptor_json},
        {"src/core/rendering/gpu_diagnostics_records.py", "_skin_3g_candidate_records._delta_to_production", "nested_functions", &src_core_rendering_gpu_diagnostics_records_skin_3g_candidate_records_delta_to_production_line_1109_482a84f4_descriptor_json},
        {"src/core/rendering/gpu_scene_helpers.py", "_CompositeModel.__init__._bb", "nested_functions", &src_core_rendering_gpu_scene_helpers_compositemodel_init_bb_line_204_ce6728e6_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_renderer_d3d12
