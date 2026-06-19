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

const NativeFunctionImplementation& gl_context_backend_candidates_line_19_4983a56d_native();
const NativeFunctionImplementation& create_moderngl_standalone_context_line_35_8986cc55_native();
const NativeFunctionImplementation& benchmark_line_14_c611fb3e_native();
const NativeFunctionImplementation& main_line_13_27f93f97_native();
const NativeFunctionImplementation& moderngl_runtime_available_line_24_aa071366_native();
const NativeFunctionImplementation& clear_prebuilt_static_gpu_mesh_data_line_209_484b9fb7_native();
const NativeFunctionImplementation& clear_prebuilt_static_gpu_model_data_line_232_f767db21_native();
const NativeFunctionImplementation& prebuilt_static_gpu_mesh_data_line_256_193fad4b_native();
const NativeFunctionImplementation& prebuild_static_gpu_mesh_data_line_273_28f9e2c6_native();
const NativeFunctionImplementation& build_vbo_data_line_345_6f99b251_native();
const NativeFunctionImplementation& render_model_autoframe_line_20_fa38dc9f_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::graphics::renderer::backend::moderngl
