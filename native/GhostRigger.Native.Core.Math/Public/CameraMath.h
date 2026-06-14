#pragma once

#include "GhostRiggerNativeCoreMath.h"

namespace ghostrigger::native::core::math::camera_math {

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

double clamp(double value, double low, double high);
double length(Vec3 value);
Vec3 normalize(Vec3 value);
Vec3 cross(Vec3 a, Vec3 b);
double dot(Vec3 a, Vec3 b);
Vec3 add(Vec3 a, Vec3 b);
Vec3 sub(Vec3 a, Vec3 b);
Vec3 mul(Vec3 value, double scalar);
Quat normalize_quat(Quat value);
Quat multiply_quat(Quat a, Quat b);
Vec3 quat_to_euler_degrees(Quat value);
Quat euler_degrees_to_quat(Vec3 euler);
Vec3 rotate_vector(Quat rotation, Vec3 value);
Quat quaternion_from_basis(Vec3 right, Vec3 up, Vec3 forward);
Quat look_at_quaternion(Vec3 position, Vec3 target);
Vec3 camera_forward(Quat value);
double focal_length_to_fov(double sensor_width_mm, double focal_length_mm);
double fov_to_focal_length(double sensor_width_mm, double fov_degrees);

} // namespace ghostrigger::native::core::math::camera_math

extern "C" {

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_normalize_vec3(
    const double* value_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_cross(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_dot(
    const double* a_xyz,
    const double* b_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_add(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_sub(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_mul(
    const double* value_xyz,
    double scalar,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_length(const double* value_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_normalize_quat(
    const double* value_xyzw,
    double* out_xyzw
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_multiply_quat(
    const double* a_xyzw,
    const double* b_xyzw,
    double* out_xyzw
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_quat_to_euler_degrees(
    const double* value_xyzw,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_euler_degrees_to_quat(
    const double* euler_xyz,
    double* out_xyzw
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_rotate_vector(
    const double* rotation_xyzw,
    const double* value_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_look_at_quaternion(
    const double* position_xyz,
    const double* target_xyz,
    double* out_xyzw
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_forward(
    const double* value_xyzw,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_focal_length_to_fov(
    double sensor_width_mm,
    double focal_length_mm
);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_fov_to_focal_length(
    double sensor_width_mm,
    double fov_degrees
);

}
