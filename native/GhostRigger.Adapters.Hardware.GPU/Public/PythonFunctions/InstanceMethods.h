#pragma once

#include <cstddef>

namespace ghostrigger::adapters::hardware::gpu {

#ifndef GHOSTRIGGER_ADAPTERS_GPU_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ADAPTERS_GPU_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ADAPTERS_GPU_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& lightmapbaker_construct_line_13_ea0e7678_native();
const NativeFunctionImplementation& lightmapgpusolver_construct_line_121_8c058229_native();
const NativeFunctionImplementation& lightmapgpusolver_solve_buffer_line_131_1afe1ce7_native();
const NativeFunctionImplementation& lightmapgpusolver_can_use_gpu_line_152_ffd61772_native();
const NativeFunctionImplementation& lightmapgpusolver_ensure_line_162_a771dede_native();
const NativeFunctionImplementation& lightmapgpusolver_solve_gpu_line_177_47133327_native();
const NativeFunctionImplementation& lightmapgpusolver_render_direct_chunk_line_210_0fddce25_native();
const NativeFunctionImplementation& lightmapgpusolver_tex2d_line_249_324b574b_native();
const NativeFunctionImplementation& lightmapgpusolver_pack_lights_line_257_2f7fdace_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::adapters::hardware::gpu
