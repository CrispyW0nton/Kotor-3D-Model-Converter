#include "Core_Math/CameraMath.h"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace ghostrigger::native::core::math::camera_math {
namespace {

constexpr double kEpsilon = 1.0e-9;

double radians(double degrees) {
    return degrees * std::numbers::pi / 180.0;
}

double degrees(double radians_value) {
    return radians_value * 180.0 / std::numbers::pi;
}

Quat axis_quat(char axis, double angle) {
    const double half = angle * 0.5;
    const double s = std::sin(half);
    const double c = std::cos(half);
    if (axis == 'X') {
        return {s, 0.0, 0.0, c};
    }
    if (axis == 'Y') {
        return {0.0, s, 0.0, c};
    }
    return {0.0, 0.0, s, c};
}

} // namespace

double clamp(double value, double low, double high) {
    return std::max(low, std::min(high, value));
}

double length(Vec3 value) {
    return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
}

Vec3 normalize(Vec3 value) {
    const double len = length(value);
    if (len <= kEpsilon || !std::isfinite(len)) {
        return {0.0, 0.0, 0.0};
    }
    return {value.x / len, value.y / len, value.z / len};
}

Vec3 cross(Vec3 a, Vec3 b) {
    return {
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
    };
}

double dot(Vec3 a, Vec3 b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

Vec3 add(Vec3 a, Vec3 b) {
    return {a.x + b.x, a.y + b.y, a.z + b.z};
}

Vec3 sub(Vec3 a, Vec3 b) {
    return {a.x - b.x, a.y - b.y, a.z - b.z};
}

Vec3 mul(Vec3 value, double scalar) {
    return {value.x * scalar, value.y * scalar, value.z * scalar};
}

Quat normalize_quat(Quat value) {
    const double n = std::sqrt(
        value.x * value.x +
        value.y * value.y +
        value.z * value.z +
        value.w * value.w
    );
    if (n <= kEpsilon || !std::isfinite(n)) {
        return {0.0, 0.0, 0.0, 1.0};
    }
    return {value.x / n, value.y / n, value.z / n, value.w / n};
}

Quat multiply_quat(Quat a, Quat b) {
    return normalize_quat({
        a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
        a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
        a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
        a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
    });
}

Vec3 quat_to_euler_degrees(Quat value) {
    const Quat q = normalize_quat(value);
    const double sinr_cosp = 2.0 * (q.w * q.x + q.y * q.z);
    const double cosr_cosp = 1.0 - 2.0 * (q.x * q.x + q.y * q.y);
    const double roll = std::atan2(sinr_cosp, cosr_cosp);

    const double sinp = 2.0 * (q.w * q.y - q.z * q.x);
    const double pitch = std::abs(sinp) >= 1.0
        ? std::copysign(std::numbers::pi / 2.0, sinp)
        : std::asin(sinp);

    const double siny_cosp = 2.0 * (q.w * q.z + q.x * q.y);
    const double cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z);
    const double yaw = std::atan2(siny_cosp, cosy_cosp);
    return {degrees(roll), degrees(pitch), degrees(yaw)};
}

Quat euler_degrees_to_quat(Vec3 euler) {
    const double rx = radians(euler.x);
    const double ry = radians(euler.y);
    const double rz = radians(euler.z);
    return multiply_quat(
        axis_quat('Z', rz),
        multiply_quat(axis_quat('Y', ry), axis_quat('X', rx))
    );
}

Vec3 rotate_vector(Quat rotation, Vec3 value) {
    const Quat q = normalize_quat(rotation);
    const double tx = 2.0 * (q.y * value.z - q.z * value.y);
    const double ty = 2.0 * (q.z * value.x - q.x * value.z);
    const double tz = 2.0 * (q.x * value.y - q.y * value.x);
    return {
        value.x + q.w * tx + (q.y * tz - q.z * ty),
        value.y + q.w * ty + (q.z * tx - q.x * tz),
        value.z + q.w * tz + (q.x * ty - q.y * tx),
    };
}

Quat quaternion_from_basis(Vec3 right, Vec3 up, Vec3 forward) {
    const Vec3 r = normalize(right);
    const Vec3 u = normalize(up);
    const Vec3 b = normalize(mul(forward, -1.0));
    const double m00 = r.x;
    const double m01 = u.x;
    const double m02 = b.x;
    const double m10 = r.y;
    const double m11 = u.y;
    const double m12 = b.y;
    const double m20 = r.z;
    const double m21 = u.z;
    const double m22 = b.z;
    const double trace = m00 + m11 + m22;

    if (trace > 0.0) {
        const double s = std::sqrt(trace + 1.0) * 2.0;
        return normalize_quat({(m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s});
    }
    if (m00 > m11 && m00 > m22) {
        const double s = std::sqrt(std::max(0.0, 1.0 + m00 - m11 - m22)) * 2.0;
        return normalize_quat({0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s});
    }
    if (m11 > m22) {
        const double s = std::sqrt(std::max(0.0, 1.0 + m11 - m00 - m22)) * 2.0;
        return normalize_quat({(m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s});
    }
    const double s = std::sqrt(std::max(0.0, 1.0 + m22 - m00 - m11)) * 2.0;
    return normalize_quat({(m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s});
}

Quat look_at_quaternion(Vec3 position, Vec3 target) {
    const Vec3 forward = normalize(sub(target, position));
    if (length(forward) <= kEpsilon) {
        return {0.0, 0.0, 0.0, 1.0};
    }

    const Vec3 world_up = {0.0, 0.0, 1.0};
    Vec3 right = normalize(cross(forward, world_up));
    if (length(right) <= kEpsilon) {
        right = normalize(cross(forward, {0.0, 1.0, 0.0}));
    }
    const Vec3 up = normalize(cross(right, forward));
    return quaternion_from_basis(right, up, forward);
}

Vec3 camera_forward(Quat value) {
    return normalize(rotate_vector(value, {0.0, 0.0, -1.0}));
}

double focal_length_to_fov(double sensor_width_mm, double focal_length_mm) {
    const double sensor = std::max(0.001, sensor_width_mm);
    const double focal = std::max(0.001, focal_length_mm);
    return degrees(2.0 * std::atan(sensor / (2.0 * focal)));
}

double fov_to_focal_length(double sensor_width_mm, double fov_degrees) {
    const double sensor = std::max(0.001, sensor_width_mm);
    const double fov = radians(clamp(fov_degrees, 1.0, 179.0));
    return sensor / (2.0 * std::tan(fov * 0.5));
}

} // namespace ghostrigger::native::core::math::camera_math

namespace {

bool read_vec3(
    const double* value,
    ghostrigger::native::core::math::camera_math::Vec3& out_value
) {
    if (value == nullptr) {
        return false;
    }
    out_value = {value[0], value[1], value[2]};
    return true;
}

bool read_quat(
    const double* value,
    ghostrigger::native::core::math::camera_math::Quat& out_value
) {
    if (value == nullptr) {
        return false;
    }
    out_value = {value[0], value[1], value[2], value[3]};
    return true;
}

int write_vec3(ghostrigger::native::core::math::camera_math::Vec3 value, double* out_value) {
    if (out_value == nullptr) {
        return 0;
    }
    out_value[0] = value.x;
    out_value[1] = value.y;
    out_value[2] = value.z;
    return 1;
}

int write_quat(ghostrigger::native::core::math::camera_math::Quat value, double* out_value) {
    if (out_value == nullptr) {
        return 0;
    }
    out_value[0] = value.x;
    out_value[1] = value.y;
    out_value[2] = value.z;
    out_value[3] = value.w;
    return 1;
}

} // namespace

extern "C" {

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_normalize_vec3(
    const double* value_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::camera_math::Vec3 value{};
    if (!read_vec3(value_xyz, value)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::camera_math::normalize(value), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_cross(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::camera_math::Vec3 a{};
    ghostrigger::native::core::math::camera_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::camera_math::cross(a, b), out_xyz);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_dot(
    const double* a_xyz,
    const double* b_xyz
) {
    ghostrigger::native::core::math::camera_math::Vec3 a{};
    ghostrigger::native::core::math::camera_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0.0;
    }
    return ghostrigger::native::core::math::camera_math::dot(a, b);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_add(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::camera_math::Vec3 a{};
    ghostrigger::native::core::math::camera_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::camera_math::add(a, b), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_sub(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::camera_math::Vec3 a{};
    ghostrigger::native::core::math::camera_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::camera_math::sub(a, b), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_mul(
    const double* value_xyz,
    double scalar,
    double* out_xyz
) {
    ghostrigger::native::core::math::camera_math::Vec3 value{};
    if (!read_vec3(value_xyz, value)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::camera_math::mul(value, scalar), out_xyz);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_length(const double* value_xyz) {
    ghostrigger::native::core::math::camera_math::Vec3 value{};
    if (!read_vec3(value_xyz, value)) {
        return 0.0;
    }
    return ghostrigger::native::core::math::camera_math::length(value);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_normalize_quat(
    const double* value_xyzw,
    double* out_xyzw
) {
    ghostrigger::native::core::math::camera_math::Quat value{};
    if (!read_quat(value_xyzw, value)) {
        return 0;
    }
    return write_quat(ghostrigger::native::core::math::camera_math::normalize_quat(value), out_xyzw);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_multiply_quat(
    const double* a_xyzw,
    const double* b_xyzw,
    double* out_xyzw
) {
    ghostrigger::native::core::math::camera_math::Quat a{};
    ghostrigger::native::core::math::camera_math::Quat b{};
    if (!read_quat(a_xyzw, a) || !read_quat(b_xyzw, b)) {
        return 0;
    }
    return write_quat(ghostrigger::native::core::math::camera_math::multiply_quat(a, b), out_xyzw);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_quat_to_euler_degrees(
    const double* value_xyzw,
    double* out_xyz
) {
    ghostrigger::native::core::math::camera_math::Quat value{};
    if (!read_quat(value_xyzw, value)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::camera_math::quat_to_euler_degrees(value), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_euler_degrees_to_quat(
    const double* euler_xyz,
    double* out_xyzw
) {
    ghostrigger::native::core::math::camera_math::Vec3 euler{};
    if (!read_vec3(euler_xyz, euler)) {
        return 0;
    }
    return write_quat(ghostrigger::native::core::math::camera_math::euler_degrees_to_quat(euler), out_xyzw);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_rotate_vector(
    const double* rotation_xyzw,
    const double* value_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::camera_math::Quat rotation{};
    ghostrigger::native::core::math::camera_math::Vec3 value{};
    if (!read_quat(rotation_xyzw, rotation) || !read_vec3(value_xyz, value)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::camera_math::rotate_vector(rotation, value), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_look_at_quaternion(
    const double* position_xyz,
    const double* target_xyz,
    double* out_xyzw
) {
    ghostrigger::native::core::math::camera_math::Vec3 position{};
    ghostrigger::native::core::math::camera_math::Vec3 target{};
    if (!read_vec3(position_xyz, position) || !read_vec3(target_xyz, target)) {
        return 0;
    }
    return write_quat(
        ghostrigger::native::core::math::camera_math::look_at_quaternion(position, target),
        out_xyzw
    );
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_camera_forward(
    const double* value_xyzw,
    double* out_xyz
) {
    ghostrigger::native::core::math::camera_math::Quat value{};
    if (!read_quat(value_xyzw, value)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::camera_math::camera_forward(value), out_xyz);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_focal_length_to_fov(
    double sensor_width_mm,
    double focal_length_mm
) {
    return ghostrigger::native::core::math::camera_math::focal_length_to_fov(
        sensor_width_mm,
        focal_length_mm
    );
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_camera_fov_to_focal_length(
    double sensor_width_mm,
    double fov_degrees
) {
    return ghostrigger::native::core::math::camera_math::fov_to_focal_length(
        sensor_width_mm,
        fov_degrees
    );
}

}
