#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::pivotcontrols {

#ifndef GHOSTRIGGER_TOOLS_PIVOTCONTROLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_PIVOTCONTROLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_PIVOTCONTROLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& fconstructe_basis_line_46_4c390260_native();
const NativeFunctionImplementation& normalize_line_56_203ee454_native();
const NativeFunctionImplementation& quat_to_basis_line_67_e86d6c6b_native();
const NativeFunctionImplementation& camera_basis_line_83_eed8416e_native();
const NativeFunctionImplementation& as_vec3_line_20_345b457a_native();
const NativeFunctionImplementation& normalize_line_24_ceecad54_native();
const NativeFunctionImplementation& ray_from_mouse_line_32_81b9804f_native();
const NativeFunctionImplementation& closest_point_on_ray_line_48_cf5b387a_native();
const NativeFunctionImplementation& closest_point_between_rays_line_56_2846b051_native();
const NativeFunctionImplementation& project_point_to_screen_line_83_7dc10361_native();
const NativeFunctionImplementation& screen_space_distance_line_88_40ef8610_native();
const NativeFunctionImplementation& axis_drag_delta_line_94_6097c784_native();
const NativeFunctionImplementation& rotation_angle_from_mouse_delta_line_123_2cd65e6d_native();
const NativeFunctionImplementation& axis_quaternion_line_137_9ff6dddc_native();
const NativeFunctionImplementation& multiply_quaternions_line_148_87a2989b_native();
const NativeFunctionImplementation& rotate_vector_line_163_a9ade386_native();
const NativeFunctionImplementation& build_translation_matrix_line_179_4dd3de4a_native();
const NativeFunctionImplementation& build_rotation_matrix_line_185_0bd655cc_native();
const NativeFunctionImplementation& build_scale_matrix_line_201_c8302f11_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::pivotcontrols
