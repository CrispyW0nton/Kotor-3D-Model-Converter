#include "Core_Math/GpuMath.h"

#include <array>
#include <cmath>

namespace {

constexpr double kEpsilon = 1.0e-9;

bool is_finite_number(double value) {
    return std::isfinite(value);
}

} // namespace

namespace ghostrigger::native::core::math::gpu_math {

namespace {

double normalize_safe(double value) {
    return is_finite_number(value) ? value : 0.0;
}

double length(Vec3 value) {
    return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
}

double length(Quat value) {
    return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z + value.w * value.w);
}

double determinant_3x3(const std::array<double, 9>& m) {
    return m[0] * (m[4] * m[8] - m[5] * m[7])
        - m[1] * (m[3] * m[8] - m[5] * m[6])
        + m[2] * (m[3] * m[7] - m[4] * m[6]);
}

} // namespace

Vec3 as_vec3(const double* values) {
    if (values == nullptr) {
        return {0.0, 0.0, 0.0};
    }
    return {
        normalize_safe(values[0]),
        normalize_safe(values[1]),
        normalize_safe(values[2]),
    };
}

Quat as_quat(const double* values) {
    if (values == nullptr) {
        return {0.0, 0.0, 0.0, 1.0};
    }
    return {
        normalize_safe(values[0]),
        normalize_safe(values[1]),
        normalize_safe(values[2]),
        normalize_safe(values[3]),
    };
}

Mat4 matrix_from_pos_quat_np(Vec3 pos, Quat quat) {
    const double qlen = length(quat);
    if (!is_finite_number(qlen) || qlen <= kEpsilon) {
        quat = {0.0, 0.0, 0.0, 1.0};
    } else {
        quat = {quat.x / qlen, quat.y / qlen, quat.z / qlen, quat.w / qlen};
    }

    const double xx = 2.0 * quat.x * quat.x;
    const double yy = 2.0 * quat.y * quat.y;
    const double zz = 2.0 * quat.z * quat.z;
    const double xy = 2.0 * quat.x * quat.y;
    const double xz = 2.0 * quat.x * quat.z;
    const double yz = 2.0 * quat.y * quat.z;
    const double wx = 2.0 * quat.w * quat.x;
    const double wy = 2.0 * quat.w * quat.y;
    const double wz = 2.0 * quat.w * quat.z;
    return {
        {
            1.0 - yy - zz,
            xy - wz,
            xz + wy,
            pos.x,
            xy + wz,
            1.0 - xx - zz,
            yz - wx,
            pos.y,
            xz - wy,
            yz + wx,
            1.0 - xx - yy,
            pos.z,
            0.0,
            0.0,
            0.0,
            1.0,
        },
    };
}

Mat4 perspective(double fov_y, double aspect, double near, double far) {
    if (!is_finite_number(fov_y) || !is_finite_number(aspect)
        || !is_finite_number(near) || !is_finite_number(far)
        || std::abs(aspect) <= kEpsilon
        || std::abs(near - far) <= kEpsilon) {
        return {
            {
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, -1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            },
        };
    }
    const double f = 1.0 / std::tan(fov_y * 0.5);
    const double nf = 1.0 / (near - far);
    return {
        {
            f / aspect, 0.0, 0.0, 0.0,
            0.0, f, 0.0, 0.0,
            0.0, 0.0, (far + near) * nf, 2.0 * far * near * nf,
            0.0, 0.0, -1.0, 0.0,
        },
    };
}

Mat4 lookat(Vec3 eye, Vec3 center, Vec3 up) {
    const Vec3 f{center.x - eye.x, center.y - eye.y, center.z - eye.z};
    const double f_len = length(f);
    if (!is_finite_number(f_len) || f_len <= kEpsilon) {
        return identity();
    }
    const Vec3 fn{f.x / f_len, f.y / f_len, f.z / f_len};

    Vec3 s{fn.y * up.z - fn.z * up.y, fn.z * up.x - fn.x * up.z, fn.x * up.y - fn.y * up.x};
    const double s_len = length(s);
    if (!is_finite_number(s_len) || s_len <= kEpsilon) {
        return identity();
    }
    s = {s.x / s_len, s.y / s_len, s.z / s_len};

    const Vec3 u{s.y * fn.z - s.z * fn.y, s.z * fn.x - s.x * fn.z, s.x * fn.y - s.y * fn.x};
    return {
        {
            s.x, s.y, s.z, -(s.x * eye.x + s.y * eye.y + s.z * eye.z),
            u.x, u.y, u.z, -(u.x * eye.x + u.y * eye.y + u.z * eye.z),
            -fn.x, -fn.y, -fn.z, fn.x * eye.x + fn.y * eye.y + fn.z * eye.z,
            0.0, 0.0, 0.0, 1.0,
        },
    };
}

Mat4 identity() {
    return {
        {
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        },
    };
}

Mat4 mul(Mat4 a, Mat4 b) {
    Mat4 result{};
    for (int row = 0; row < 4; ++row) {
        for (int col = 0; col < 4; ++col) {
            double value = 0.0;
            for (int axis = 0; axis < 4; ++axis) {
                value += a.values[row * 4 + axis] * b.values[axis * 4 + col];
            }
            result.values[row * 4 + col] = value;
        }
    }
    return result;
}

Mat3 normal_matrix(Mat4 model_matrix) {
    const std::array<double, 9> m{
        model_matrix.values[0], model_matrix.values[1], model_matrix.values[2],
        model_matrix.values[4], model_matrix.values[5], model_matrix.values[6],
        model_matrix.values[8], model_matrix.values[9], model_matrix.values[10],
    };
    const double det = determinant_3x3(m);
    if (!is_finite_number(det) || std::abs(det) <= kEpsilon) {
        return {
            {
                1.0, 0.0, 0.0,
                0.0, 1.0, 0.0,
                0.0, 0.0, 1.0,
            },
        };
    }
    const double invdet = 1.0 / det;
    const double inv00 = (m[4] * m[8] - m[5] * m[7]) * invdet;
    const double inv01 = -(m[1] * m[8] - m[2] * m[7]) * invdet;
    const double inv02 = (m[1] * m[5] - m[2] * m[4]) * invdet;
    const double inv10 = -(m[3] * m[8] - m[5] * m[6]) * invdet;
    const double inv11 = (m[0] * m[8] - m[2] * m[6]) * invdet;
    const double inv12 = -(m[0] * m[5] - m[2] * m[3]) * invdet;
    const double inv20 = (m[3] * m[7] - m[4] * m[6]) * invdet;
    const double inv21 = -(m[0] * m[7] - m[1] * m[6]) * invdet;
    const double inv22 = (m[0] * m[4] - m[1] * m[3]) * invdet;
    return {
        {
            inv00, inv10, inv20,
            inv01, inv11, inv21,
            inv02, inv12, inv22,
        },
    };
}

} // namespace ghostrigger::native::core::math::gpu_math

namespace {

bool read_vec3(
    const double* source,
    ghostrigger::native::core::math::gpu_math::Vec3& out_value
) {
    if (source == nullptr) {
        return false;
    }
    out_value = ghostrigger::native::core::math::gpu_math::as_vec3(source);
    return true;
}

bool read_quat(
    const double* source,
    ghostrigger::native::core::math::gpu_math::Quat& out_value
) {
    if (source == nullptr) {
        return false;
    }
    out_value = ghostrigger::native::core::math::gpu_math::as_quat(source);
    return true;
}

int write_mat4(
    ghostrigger::native::core::math::gpu_math::Mat4 value,
    double* out_value
) {
    if (out_value == nullptr) {
        return 0;
    }
    for (int i = 0; i < 16; ++i) {
        out_value[i] = value.values[i];
    }
    return 1;
}

int write_mat4_as_float32(
    ghostrigger::native::core::math::gpu_math::Mat4 value,
    double* out_value
) {
    if (out_value == nullptr) {
        return 0;
    }
    for (int i = 0; i < 16; ++i) {
        out_value[i] = static_cast<double>(static_cast<float>(value.values[i]));
    }
    return 1;
}

int write_mat3(
    ghostrigger::native::core::math::gpu_math::Mat3 value,
    double* out_value
) {
    if (out_value == nullptr) {
        return 0;
    }
    for (int i = 0; i < 9; ++i) {
        out_value[i] = value.values[i];
    }
    return 1;
}

int write_mat3_as_float32(
    ghostrigger::native::core::math::gpu_math::Mat3 value,
    double* out_value
) {
    if (out_value == nullptr) {
        return 0;
    }
    for (int i = 0; i < 9; ++i) {
        out_value[i] = static_cast<double>(static_cast<float>(value.values[i]));
    }
    return 1;
}

bool is_finite_matrix_3x3(const ghostrigger::native::core::math::gpu_math::Mat3& value) {
    for (int i = 0; i < 9; ++i) {
        if (!std::isfinite(value.values[i])) {
            return false;
        }
    }
    return true;
}

bool is_finite_matrix_4x4(const ghostrigger::native::core::math::gpu_math::Mat4& value) {
    for (int i = 0; i < 16; ++i) {
        if (!std::isfinite(value.values[i])) {
            return false;
        }
    }
    return true;
}

bool is_finite_matrix(const ghostrigger::native::core::math::gpu_math::Mat4& value) {
    return is_finite_matrix_4x4(value);
}

bool is_finite_vector(const ghostrigger::native::core::math::gpu_math::Vec3& value) {
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

bool is_finite_vector(const ghostrigger::native::core::math::gpu_math::Quat& value) {
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z) && std::isfinite(value.w);
}

} // namespace

extern "C" {

GR_NATIVE_CORE_MATH_API int gr_native_core_math_matrix_from_pos_quat_np(
    const double* pos_xyz,
    const double* quat_xyzw,
    double* out_matrix
) {
    ghostrigger::native::core::math::gpu_math::Vec3 pos{};
    ghostrigger::native::core::math::gpu_math::Quat quat{};
    if (!read_vec3(pos_xyz, pos) || !read_quat(quat_xyzw, quat)) {
        return 0;
    }
    if (!is_finite_vector(pos) || !is_finite_vector(quat)) {
        return 0;
    }
    return write_mat4(ghostrigger::native::core::math::gpu_math::matrix_from_pos_quat_np(pos, quat), out_matrix);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat4_perspective(
    double fov_y,
    double aspect,
    double near,
    double far,
    double* out_matrix
) {
    const auto result = ghostrigger::native::core::math::gpu_math::perspective(fov_y, aspect, near, far);
    if (!is_finite_matrix(result)) {
        return 0;
    }
    return write_mat4_as_float32(result, out_matrix);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat4_lookat(
    const double* eye_xyz,
    const double* center_xyz,
    const double* up_xyz,
    double* out_matrix
) {
    ghostrigger::native::core::math::gpu_math::Vec3 eye{};
    ghostrigger::native::core::math::gpu_math::Vec3 center{};
    ghostrigger::native::core::math::gpu_math::Vec3 up{};
    if (!read_vec3(eye_xyz, eye) || !read_vec3(center_xyz, center) || !read_vec3(up_xyz, up)) {
        return 0;
    }
    const auto result = ghostrigger::native::core::math::gpu_math::lookat(eye, center, up);
    if (!is_finite_matrix(result) || !is_finite_vector(up)) {
        return 0;
    }
    return write_mat4_as_float32(result, out_matrix);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat4_identity(
    double* out_matrix
) {
    return write_mat4(ghostrigger::native::core::math::gpu_math::identity(), out_matrix);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat4_mul(
    const double* a_matrix,
    const double* b_matrix,
    double* out_matrix
) {
    if (a_matrix == nullptr || b_matrix == nullptr) {
        return 0;
    }
    ghostrigger::native::core::math::gpu_math::Mat4 a{{
        a_matrix[0], a_matrix[1], a_matrix[2], a_matrix[3],
        a_matrix[4], a_matrix[5], a_matrix[6], a_matrix[7],
        a_matrix[8], a_matrix[9], a_matrix[10], a_matrix[11],
        a_matrix[12], a_matrix[13], a_matrix[14], a_matrix[15],
    }};
    ghostrigger::native::core::math::gpu_math::Mat4 b{{
        b_matrix[0], b_matrix[1], b_matrix[2], b_matrix[3],
        b_matrix[4], b_matrix[5], b_matrix[6], b_matrix[7],
        b_matrix[8], b_matrix[9], b_matrix[10], b_matrix[11],
        b_matrix[12], b_matrix[13], b_matrix[14], b_matrix[15],
    }};
    if (!is_finite_matrix(a) || !is_finite_matrix(b)) {
        return 0;
    }
    return write_mat4(ghostrigger::native::core::math::gpu_math::mul(a, b), out_matrix);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_mat3_normal(
    const double* model_matrix,
    double* out_matrix
) {
    if (model_matrix == nullptr) {
        return 0;
    }
    ghostrigger::native::core::math::gpu_math::Mat4 matrix{{
        model_matrix[0], model_matrix[1], model_matrix[2], model_matrix[3],
        model_matrix[4], model_matrix[5], model_matrix[6], model_matrix[7],
        model_matrix[8], model_matrix[9], model_matrix[10], model_matrix[11],
        model_matrix[12], model_matrix[13], model_matrix[14], model_matrix[15],
    }};
    if (!is_finite_matrix(matrix)) {
        return 0;
    }
    return write_mat3_as_float32(ghostrigger::native::core::math::gpu_math::normal_matrix(matrix), out_matrix);
}

}
