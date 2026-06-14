#pragma once

#include "GhostRiggerNativeCoreMath.h"

namespace ghostrigger::native::core::math::gpu_math {

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

struct Mat3 {
    double values[9];
};

struct Mat4 {
    double values[16];
};

Vec3 as_vec3(const double* values);
Quat as_quat(const double* values);
Mat4 matrix_from_pos_quat_np(Vec3 pos, Quat quat);
Mat4 perspective(double fov_y, double aspect, double near, double far);
Mat4 lookat(Vec3 eye, Vec3 center, Vec3 up);
Mat4 identity();
Mat4 mul(Mat4 a, Mat4 b);
Mat3 normal_matrix(Mat4 model_matrix);

} // namespace ghostrigger::native::core::math::gpu_math

extern "C" {

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

}
