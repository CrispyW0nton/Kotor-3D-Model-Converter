#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_scene_axis_mode_finite_basis_line_46_4c390260_descriptor_json();
const char* src_core_scene_axis_mode_normalize_line_56_203ee454_descriptor_json();
const char* src_core_scene_axis_mode_quat_to_basis_line_67_e86d6c6b_descriptor_json();
const char* src_core_scene_axis_mode_camera_basis_line_83_eed8416e_descriptor_json();
const char* src_math_transform_math_as_vec3_line_20_345b457a_descriptor_json();
const char* src_math_transform_math_normalize_line_24_ceecad54_descriptor_json();
const char* src_math_transform_math_ray_from_mouse_line_32_81b9804f_descriptor_json();
const char* src_math_transform_math_closest_point_on_ray_line_48_cf5b387a_descriptor_json();
const char* src_math_transform_math_closest_point_between_rays_line_56_2846b051_descriptor_json();
const char* src_math_transform_math_project_point_to_screen_line_83_7dc10361_descriptor_json();
const char* src_math_transform_math_screen_space_distance_line_88_40ef8610_descriptor_json();
const char* src_math_transform_math_axis_drag_delta_line_94_6097c784_descriptor_json();
const char* src_math_transform_math_rotation_angle_from_mouse_delta_line_123_2cd65e6d_descriptor_json();
const char* src_math_transform_math_axis_quaternion_line_137_9ff6dddc_descriptor_json();
const char* src_math_transform_math_multiply_quaternions_line_148_87a2989b_descriptor_json();
const char* src_math_transform_math_rotate_vector_line_163_a9ade386_descriptor_json();
const char* src_math_transform_math_build_translation_matrix_line_179_4dd3de4a_descriptor_json();
const char* src_math_transform_math_build_rotation_matrix_line_185_0bd655cc_descriptor_json();
const char* src_math_transform_math_build_scale_matrix_line_201_c8302f11_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols
