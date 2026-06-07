#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_adapters_gpu {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_gpu_lightmap_baker_lightmapbaker_init_line_13_ea0e7678_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_lightmapgpusolver_init_line_121_8c058229_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_lightmapgpusolver_solve_buffer_line_131_1afe1ce7_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_lightmapgpusolver_can_use_gpu_line_152_ffd61772_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_lightmapgpusolver_ensure_line_162_a771dede_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_lightmapgpusolver_solve_gpu_line_177_47133327_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_lightmapgpusolver_render_direct_chunk_line_210_0fddce25_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_lightmapgpusolver_tex2d_line_249_324b574b_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_lightmapgpusolver_pack_lights_line_257_2f7fdace_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_adapters_gpu
