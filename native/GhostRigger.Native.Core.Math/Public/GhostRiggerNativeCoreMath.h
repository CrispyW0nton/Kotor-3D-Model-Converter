#pragma once

#include <cstdint>

#if defined(_WIN32)
#if defined(NATIVE_CORE_MATH_EXPORTS)
#define GR_NATIVE_CORE_MATH_API __declspec(dllexport)
#else
#define GR_NATIVE_CORE_MATH_API __declspec(dllimport)
#endif
#else
#define GR_NATIVE_CORE_MATH_API
#endif

extern "C" {

GR_NATIVE_CORE_MATH_API const char* gr_native_core_math_version();
GR_NATIVE_CORE_MATH_API const char* gr_native_core_math_capabilities_json();
GR_NATIVE_CORE_MATH_API int gr_native_core_math_bounds_from_points(
    const float* xyz_points,
    std::uint32_t point_count,
    float* out_min_xyz,
    float* out_max_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_bounds_center(
    const float* min_xyz,
    const float* max_xyz,
    float* out_center_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_point(
    const float* matrix4x4_row_major,
    const float* point_xyz,
    float* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_normalize_vec3(
    const double* value_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_cross(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_dot(
    const double* a_xyz,
    const double* b_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_add(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_sub(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_mul(
    const double* value_xyz,
    double scalar,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_length(const double* value_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_normalize_quat(
    const double* value_xyzw,
    double* out_xyzw);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_multiply_quat(
    const double* a_xyzw,
    const double* b_xyzw,
    double* out_xyzw);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_quat_to_euler_degrees(
    const double* value_xyzw,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_euler_degrees_to_quat(
    const double* euler_xyz,
    double* out_xyzw);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_rotate_vector(
    const double* rotation_xyzw,
    const double* value_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_look_at_quaternion(
    const double* position_xyz,
    const double* target_xyz,
    double* out_xyzw);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_forward(
    const double* value_xyzw,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_focal_length_to_fov(
    double sensor_width_mm,
    double focal_length_mm);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_fov_to_focal_length(
    double sensor_width_mm,
    double fov_degrees);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_normalize_vec3(
    const double* value_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API const char* gr_native_core_math_frame_clean_texture_name(const char* name);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_cross(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_dot(
    const double* a_xyz,
    const double* b_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_sub(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_add(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_clamp(
    double value,
    double low,
    double high);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_lerp(
    double a,
    double b,
    double t);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_unwrap_uv(
    double base,
    double other);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_edge_has_seam(
    double a,
    double b);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_vflip_nontiled(
    double v,
    double texture_height);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_vflip_tiled(
    double v,
    double tile_v,
    double source_height);
GR_NATIVE_CORE_MATH_API std::uint32_t gr_native_core_math_frame_float_to_sort_key(double value);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_compute_screen_size_ratio(
    const double* bounds_min_xyz,
    const double* bounds_max_xyz,
    const double* view_origin_xyz,
    double fov_vertical_rad,
    int viewport_height);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_module_anchor_relative_position(
    const double* room_lyt_xyz,
    const double* anchor_lyt_xyz,
    const double* anchor_scene_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_matrix_from_pos_quat_np(
    const double* pos_xyz,
    const double* quat_xyzw,
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat4_perspective(
    double fov_y,
    double aspect,
    double near,
    double far,
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat4_lookat(
    const double* eye_xyz,
    const double* center_xyz,
    const double* up_xyz,
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat4_identity(
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat4_mul(
    const double* a_matrix,
    const double* b_matrix,
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat3_normal(
    const double* model_matrix,
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_as_vec3(
    const double* values,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_normalize(
    const double* value_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_closest_point_on_ray(
    const double* origin_xyz,
    const double* direction_xyz,
    const double* point_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_closest_point_between_rays(
    const double* origin_a_xyz,
    const double* direction_a_xyz,
    const double* origin_b_xyz,
    const double* direction_b_xyz,
    double* out_point_a_xyz,
    double* out_point_b_xyz);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_transform_screen_space_distance(
    double ax,
    double ay,
    double bx,
    double by);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_transform_rotation_angle_from_mouse_delta(
    double start_x,
    double start_y,
    double x,
    double y,
    double center_x,
    double center_y,
    int has_center);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_axis_quaternion(
    char axis,
    double angle,
    double* out_xyzw);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_multiply_quaternions(
    const double* a_xyzw,
    const double* b_xyzw,
    double* out_xyzw);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_rotate_vector(
    const double* rotation_xyzw,
    const double* vector_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_translation_matrix(
    const double* delta_xyz,
    double* out_matrix);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_rotation_matrix(
    char axis,
    double angle,
    double* out_matrix);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_scale_matrix_scalar(
    double scale,
    double* out_matrix);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_scale_matrix_vector(
    const double* scale_xyz,
    double* out_matrix);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_normalize(
    const double* value_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_cross(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_viewcube_dot(
    const double* a_xyz,
    const double* b_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_azimuth_elevation_from_direction(
    const double* direction_xyz,
    double* out_azimuth_degrees,
    double* out_elevation_degrees);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_action_from_view_name(
    const char* view_name,
    int* out_action);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_target_for_action(
    int action,
    double* out_azimuth_degrees,
    double* out_elevation_degrees);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_view_direction_from_angles(
    double azimuth,
    double elevation,
    double* out_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_camera_basis_from_angles(
    double azimuth,
    double elevation,
    double* out_right_xyz,
    double* out_up_xyz,
    double* out_forward_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_view_orientation_quaternion(
    double azimuth,
    double elevation,
    double* out_xyzw);

}
