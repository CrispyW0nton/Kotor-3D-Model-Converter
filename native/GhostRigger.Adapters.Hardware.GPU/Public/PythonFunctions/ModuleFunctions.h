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

const NativeFunctionImplementation& kind_code_line_278_064e698f_native();
const NativeFunctionImplementation& vec3_line_291_f6acbc46_native();
const NativeFunctionImplementation& gl_context_backend_candidates_line_19_4983a56d_native();
const NativeFunctionImplementation& create_moderngl_standalone_context_line_35_8986cc55_native();
const NativeFunctionImplementation& gr_gpu_probe_line_16_3850cbae_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::adapters::hardware::gpu
