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

}
