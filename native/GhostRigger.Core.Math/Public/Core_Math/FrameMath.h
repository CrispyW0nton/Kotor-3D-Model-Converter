#pragma once

#include "Core_Math/GhostRiggerNativeCoreMath.h"

#include <cstdint>
#include <string>

namespace ghostrigger::native::core::math::frame_math {

struct Vec3 {
    double x;
    double y;
    double z;
};

Vec3 normalize(Vec3 value);
std::string clean_texture_name(const char* name);
Vec3 cross(Vec3 a, Vec3 b);
double dot(Vec3 a, Vec3 b);
Vec3 sub(Vec3 a, Vec3 b);
Vec3 add(Vec3 a, Vec3 b);
double clamp(double value, double low, double high);
double lerp(double a, double b, double t);
double unwrap_uv(double base, double other);
bool edge_has_seam(double a, double b);
double vflip_nontiled(double v, double texture_height);
double vflip_tiled(double v, double tile_v, double source_height);
std::uint32_t float_to_sort_key(double value);
double compute_screen_size_ratio(
    Vec3 bounds_min,
    Vec3 bounds_max,
    Vec3 view_origin,
    double fov_vertical_rad,
    int viewport_height
);

} // namespace ghostrigger::native::core::math::frame_math

extern "C" {

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
