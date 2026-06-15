#pragma once

#include "GhostRiggerNativeCoreMath.h"

#include <cstdint>
#include <utility>

namespace ghostrigger::native::core::math::transform_math {

struct Vec3 {
    double x;
    double y;
    double z;
};

struct Quat {
    double x;
    double y;
    double z;
    double w;
};

struct Mat4 {
    double values[16];
};

constexpr char kAxisXLabel = 'X';
constexpr char kAxisYLabel = 'Y';
constexpr char kAxisZLabel = 'Z';

Vec3 as_vec3(const double* values);
Vec3 normalize(Vec3 value);
Vec3 closest_point_on_ray(Vec3 origin, Vec3 direction, Vec3 point);
std::pair<Vec3, Vec3> closest_point_between_rays(
    Vec3 origin_a,
    Vec3 direction_a,
    Vec3 origin_b,
    Vec3 direction_b
);
double screen_space_distance(double ax, double ay, double bx, double by);
double rotation_angle_from_mouse_delta(double start_x, double start_y, double x, double y, double center_x, double center_y, bool has_center);
Quat axis_quaternion(char axis, double angle);
Quat multiply_quaternions(Quat a, Quat b);
Vec3 rotate_vector(Quat rotation, Vec3 vector);
Mat4 build_translation_matrix(Vec3 delta);
Mat4 build_rotation_matrix(char axis, double angle);
Mat4 build_scale_matrix_scalar(double scale);
Mat4 build_scale_matrix_vector(Vec3 scale);

} // namespace ghostrigger::native::core::math::transform_math

extern "C" {

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_as_vec3(
    const double* values,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_normalize(
    const double* value_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_closest_point_on_ray(
    const double* origin_xyz,
    const double* direction_xyz,
    const double* point_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_closest_point_between_rays(
    const double* origin_a_xyz,
    const double* direction_a_xyz,
    const double* origin_b_xyz,
    const double* direction_b_xyz,
    double* out_point_a_xyz,
    double* out_point_b_xyz
);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_transform_screen_space_distance(
    double ax,
    double ay,
    double bx,
    double by
);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_transform_rotation_angle_from_mouse_delta(
    double start_x,
    double start_y,
    double x,
    double y,
    double center_x,
    double center_y,
    int has_center
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_axis_quaternion(
    char axis,
    double angle,
    double* out_xyzw
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_multiply_quaternions(
    const double* a_xyzw,
    const double* b_xyzw,
    double* out_xyzw
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_rotate_vector(
    const double* rotation_xyzw,
    const double* vector_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_translation_matrix(
    const double* delta_xyz,
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_rotation_matrix(
    char axis,
    double angle,
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_scale_matrix_scalar(
    double scale,
    double* out_matrix
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_scale_matrix_vector(
    const double* scale_xyz,
    double* out_matrix
);

}
