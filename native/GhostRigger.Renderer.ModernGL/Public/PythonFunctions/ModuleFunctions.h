#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_moderngl {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_gpu_moderngl_context_gl_context_backend_candidates_line_19_4983a56d_descriptor_json();
const char* src_adapters_gpu_moderngl_context_create_moderngl_standalone_context_line_35_8986cc55_descriptor_json();
const char* src_adapters_rendering_moderngl_benchmark_benchmark_line_14_c611fb3e_descriptor_json();
const char* src_adapters_rendering_moderngl_cli_main_line_13_27f93f97_descriptor_json();
const char* src_adapters_rendering_moderngl_legacy_bridge_moderngl_runtime_available_line_24_aa071366_descriptor_json();
const char* src_adapters_rendering_moderngl_resources_clear_prebuilt_static_gpu_mesh_data_line_209_484b9fb7_descriptor_json();
const char* src_adapters_rendering_moderngl_resources_clear_prebuilt_static_gpu_model_data_line_232_f767db21_descriptor_json();
const char* src_adapters_rendering_moderngl_resources_prebuilt_static_gpu_mesh_data_line_256_193fad4b_descriptor_json();
const char* src_adapters_rendering_moderngl_resources_prebuild_static_gpu_mesh_data_line_273_28f9e2c6_descriptor_json();
const char* src_adapters_rendering_moderngl_resources_build_vbo_data_line_345_6f99b251_descriptor_json();
const char* src_adapters_rendering_moderngl_scene_helpers_render_model_autoframe_line_20_fa38dc9f_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_moderngl
