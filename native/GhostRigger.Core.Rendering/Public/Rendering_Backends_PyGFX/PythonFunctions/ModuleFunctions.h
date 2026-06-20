#pragma once

#include <cstddef>

namespace ghostrigger::core::rendering::backends::pygfx {

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

const NativeFunctionImplementation& gpu_runtime_imported_line_26_47280230_native();
const NativeFunctionImplementation& prepare_pygfx_wgpu_environment_line_32_ef7d19d9_native();
const NativeFunctionImplementation& probe_script_line_73_458ebad6_native();
const NativeFunctionImplementation& getattr_line_35_3a809ba4_native();
const NativeFunctionImplementation& dir_line_45_972c5fdd_native();
const NativeFunctionImplementation& load_mesh_shader_line_6_2d673ba0_native();
const NativeFunctionImplementation& load_skinned_mesh_shader_line_14_843f9a71_native();
const NativeFunctionImplementation& rgb_float_line_127_9d78f9a4_native();
const NativeFunctionImplementation& blend_rgb_line_131_eeb9479a_native();
const NativeFunctionImplementation& relative_luma_line_136_ac138b90_native();
const NativeFunctionImplementation& rgba8_line_141_bd9365fb_native();
const NativeFunctionImplementation& point_distance_line_145_c54244b6_native();
const NativeFunctionImplementation& joint_marker_segments_line_149_bb4dab87_native();
const NativeFunctionImplementation& srgb_channel_to_linear_line_162_43d6320e_native();
const NativeFunctionImplementation& srgb_to_linear_line_169_cbc572d3_native();
const NativeFunctionImplementation& format_is_srgb_line_176_977aa9e8_native();
const NativeFunctionImplementation& mat4_perspective_wgpu_line_180_30daf050_native();
const NativeFunctionImplementation& mat4_lookat_line_193_5cb75700_native();
const NativeFunctionImplementation& mat4_tobytes_line_222_f9135a93_native();
const NativeFunctionImplementation& adapter_info_dict_line_228_dcc235f2_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::rendering::backends::pygfx
