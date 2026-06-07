#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_d3d12 {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_rendering_gpu_diagnostics_records_texture_content_stats_sample_line_180_6862de25_descriptor_json();
const char* src_core_rendering_gpu_diagnostics_records_skin_3g_candidate_records_norm_pos_line_1096_04f54701_descriptor_json();
const char* src_core_rendering_gpu_diagnostics_records_skin_3g_candidate_records_delta_to_production_line_1109_482a84f4_descriptor_json();
const char* src_core_rendering_gpu_scene_helpers_compositemodel_init_bb_line_204_ce6728e6_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_d3d12
