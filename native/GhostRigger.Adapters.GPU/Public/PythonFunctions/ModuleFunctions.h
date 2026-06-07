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

const char* src_adapters_gpu_lightmap_gpu_solver_kind_code_line_278_064e698f_descriptor_json();
const char* src_adapters_gpu_lightmap_gpu_solver_vec3_line_291_f6acbc46_descriptor_json();
const char* src_adapters_gpu_moderngl_context_gl_context_backend_candidates_line_19_4983a56d_descriptor_json();
const char* src_adapters_gpu_moderngl_context_create_moderngl_standalone_context_line_35_8986cc55_descriptor_json();
const char* src_adapters_gpu_viewport_probe_gr_gpu_probe_line_16_3850cbae_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_adapters_gpu
