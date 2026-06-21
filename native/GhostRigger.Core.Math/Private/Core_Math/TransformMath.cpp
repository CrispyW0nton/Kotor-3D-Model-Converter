#include "Core_Math/TransformMath.h"

#include <algorithm>
#include <cmath>
#include <numbers>
#include <utility>

namespace ghostrigger::native::core::math::transform_math {
namespace {

constexpr double kEpsilon = 1.0e-9;

double length(Vec3 value) {
    return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
}

void set_xyz(Vec3 value, double* out_xyz) {
    if (out_xyz != nullptr) {
        out_xyz[0] = value.x;
        out_xyz[1] = value.y;
        out_xyz[2] = value.z;
    }
}

void set_mat4(Mat4 value, double* out_matrix) {
    if (out_matrix != nullptr) {
        for (int i = 0; i < 16; ++i) {
            out_matrix[i] = value.values[i];
        }
    }
}

Vec3 as_axis_vec(const char axis) {
    if (axis == 'X' || axis == 'x') {
        return {1.0, 0.0, 0.0};
    }
    if (axis == kAxisYLabel || axis == 'y') {
        return {0.0, 1.0, 0.0};
    }
    if (axis == kAxisZLabel || axis == 'z') {
        return {0.0, 0.0, 1.0};
    }
    return {0.0, 0.0, 1.0};
}

} // namespace

Vec3 as_vec3(const double* values) {
    if (values == nullptr) {
        return {0.0, 0.0, 0.0};
    }
    return {values[0], values[1], values[2]};
}

Vec3 normalize(Vec3 value) {
    const double len = length(value);
    if (len <= kEpsilon || !std::isfinite(len)) {
        return {0.0, 0.0, 0.0};
    }
    return {value.x / len, value.y / len, value.z / len};
}

Vec3 closest_point_on_ray(Vec3 origin, Vec3 direction, Vec3 point) {
    const Vec3 dir = normalize(direction);
    const double t = std::max(0.0, (point.x - origin.x) * dir.x + (point.y - origin.y) * dir.y + (point.z - origin.z) * dir.z);
    return {
        origin.x + dir.x * t,
        origin.y + dir.y * t,
        origin.z + dir.z * t,
    };
}

std::pair<Vec3, Vec3> closest_point_between_rays(
    Vec3 origin_a,
    Vec3 direction_a,
    Vec3 origin_b,
    Vec3 direction_b
) {
    const Vec3 d1 = normalize(direction_a);
    const Vec3 d2 = normalize(direction_b);
    const Vec3 r = {origin_a.x - origin_b.x, origin_a.y - origin_b.y, origin_a.z - origin_b.z};
    const double a = d1.x * d1.x + d1.y * d1.y + d1.z * d1.z;
    const double e = d2.x * d2.x + d2.y * d2.y + d2.z * d2.z;
    const double b = d1.x * d2.x + d1.y * d2.y + d1.z * d2.z;
    const double c = d1.x * r.x + d1.y * r.y + d1.z * r.z;
    const double f = d2.x * r.x + d2.y * r.y + d2.z * r.z;
    const double denom = a * e - b * b;
    double s = 0.0;
    double t = 0.0;
    if (std::abs(denom) <= kEpsilon) {
        t = f / (e + kEpsilon);
    } else {
        s = (b * f - c * e) / denom;
        t = (a * f - b * c) / denom;
    }
    s = std::max(0.0, s);
    t = std::max(0.0, t);
    return {
        {
            origin_a.x + d1.x * s,
            origin_a.y + d1.y * s,
            origin_a.z + d1.z * s,
        },
        {
            origin_b.x + d2.x * t,
            origin_b.y + d2.y * t,
            origin_b.z + d2.z * t,
        },
    };
}

double screen_space_distance(double ax, double ay, double bx, double by) {
    const double dx = ax - bx;
    const double dy = ay - by;
    return std::sqrt(dx * dx + dy * dy);
}

double rotation_angle_from_mouse_delta(double start_x, double start_y, double x, double y, double center_x, double center_y, bool has_center) {
    if (has_center) {
        const double a0 = std::atan2(start_y - center_y, start_x - center_x);
        const double a1 = std::atan2(y - center_y, x - center_x);
        const double delta = a1 - a0;
        const double two_pi = std::numbers::pi * 2.0;
        return std::fmod(delta + std::numbers::pi, two_pi) - std::numbers::pi;
    }
    return (x - start_x) * 0.01;
}

Quat axis_quaternion(char axis, double angle) {
    const Vec3 axis_vec = as_axis_vec(axis);
    const double half = angle * 0.5;
    const double s = std::sin(half);
    return {
        axis_vec.x * s,
        axis_vec.y * s,
        axis_vec.z * s,
        std::cos(half),
    };
}

Quat multiply_quaternions(Quat a, Quat b) {
    const Quat product {
        a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
        a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
        a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
        a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
    };
    const double n = std::sqrt(
        product.x * product.x +
        product.y * product.y +
        product.z * product.z +
        product.w * product.w
    );
    if (n <= kEpsilon || !std::isfinite(n)) {
        return {0.0, 0.0, 0.0, 1.0};
    }
    return {
        product.x / n,
        product.y / n,
        product.z / n,
        product.w / n,
    };
}

Vec3 rotate_vector(Quat rotation, Vec3 vector) {
    const double tx = 2.0 * (rotation.y * vector.z - rotation.z * vector.y);
    const double ty = 2.0 * (rotation.z * vector.x - rotation.x * vector.z);
    const double tz = 2.0 * (rotation.x * vector.y - rotation.y * vector.x);
    return {
        vector.x + rotation.w * tx + (rotation.y * tz - rotation.z * ty),
        vector.y + rotation.w * ty + (rotation.z * tx - rotation.x * tz),
        vector.z + rotation.w * tz + (rotation.x * ty - rotation.y * tx),
    };
}

Mat4 build_translation_matrix(Vec3 delta) {
    return {
        {
            1.0, 0.0, 0.0, delta.x,
            0.0, 1.0, 0.0, delta.y,
            0.0, 0.0, 1.0, delta.z,
            0.0, 0.0, 0.0, 1.0,
        },
    };
}

Mat4 build_rotation_matrix(char axis, double angle) {
    const Vec3 axis_vec = as_axis_vec(axis);
    const double c = std::cos(angle);
    const double s = std::sin(angle);
    const double t = 1.0 - c;
    return {
        {
            t * axis_vec.x * axis_vec.x + c,
            t * axis_vec.x * axis_vec.y - s * axis_vec.z,
            t * axis_vec.x * axis_vec.z + s * axis_vec.y,
            0.0,
            t * axis_vec.x * axis_vec.y + s * axis_vec.z,
            t * axis_vec.y * axis_vec.y + c,
            t * axis_vec.y * axis_vec.z - s * axis_vec.x,
            0.0,
            t * axis_vec.x * axis_vec.z - s * axis_vec.y,
            t * axis_vec.y * axis_vec.z + s * axis_vec.x,
            t * axis_vec.z * axis_vec.z + c,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        },
    };
}

Mat4 build_scale_matrix_scalar(double scale) {
    return {
        {
            scale, 0.0, 0.0, 0.0,
            0.0, scale, 0.0, 0.0,
            0.0, 0.0, scale, 0.0,
            0.0, 0.0, 0.0, 1.0,
        },
    };
}

Mat4 build_scale_matrix_vector(Vec3 scale) {
    return {
        {
            scale.x, 0.0, 0.0, 0.0,
            0.0, scale.y, 0.0, 0.0,
            0.0, 0.0, scale.z, 0.0,
            0.0, 0.0, 0.0, 1.0,
        },
    };
}

} // namespace ghostrigger::native::core::math::transform_math

namespace {

bool read_vec3(const double* source, ghostrigger::native::core::math::transform_math::Vec3& out_value) {
    if (source == nullptr) {
        return false;
    }
    out_value = ghostrigger::native::core::math::transform_math::as_vec3(source);
    return true;
}

bool read_quat(const double* source, ghostrigger::native::core::math::transform_math::Quat& out_value) {
    if (source == nullptr) {
        return false;
    }
    out_value = {
        source[0],
        source[1],
        source[2],
        source[3],
    };
    return true;
}

int write_vec3(const ghostrigger::native::core::math::transform_math::Vec3& value, double* out_value) {
    if (out_value == nullptr) {
        return 0;
    }
    out_value[0] = value.x;
    out_value[1] = value.y;
    out_value[2] = value.z;
    return 1;
}

int write_quat(const ghostrigger::native::core::math::transform_math::Quat& value, double* out_value) {
    if (out_value == nullptr) {
        return 0;
    }
    out_value[0] = value.x;
    out_value[1] = value.y;
    out_value[2] = value.z;
    out_value[3] = value.w;
    return 1;
}

int write_matrix(const ghostrigger::native::core::math::transform_math::Mat4& value, double* out_value) {
    if (out_value == nullptr) {
        return 0;
    }
    for (int index = 0; index < 16; ++index) {
        out_value[index] = value.values[index];
    }
    return 1;
}

} // namespace

extern "C" {

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_as_vec3(
    const double* values,
    double* out_xyz
) {
    return write_vec3(ghostrigger::native::core::math::transform_math::as_vec3(values), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_normalize(
    const double* value_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::transform_math::Vec3 value{};
    if (!read_vec3(value_xyz, value)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::transform_math::normalize(value), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_closest_point_on_ray(
    const double* origin_xyz,
    const double* direction_xyz,
    const double* point_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::transform_math::Vec3 origin{};
    ghostrigger::native::core::math::transform_math::Vec3 direction{};
    ghostrigger::native::core::math::transform_math::Vec3 point{};
    if (!read_vec3(origin_xyz, origin) || !read_vec3(direction_xyz, direction) || !read_vec3(point_xyz, point)) {
        return 0;
    }
    return write_vec3(
        ghostrigger::native::core::math::transform_math::closest_point_on_ray(
            origin,
            direction,
            point
        ),
        out_xyz
    );
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_closest_point_between_rays(
    const double* origin_a_xyz,
    const double* direction_a_xyz,
    const double* origin_b_xyz,
    const double* direction_b_xyz,
    double* out_point_a_xyz,
    double* out_point_b_xyz
) {
    ghostrigger::native::core::math::transform_math::Vec3 origin_a{};
    ghostrigger::native::core::math::transform_math::Vec3 direction_a{};
    ghostrigger::native::core::math::transform_math::Vec3 origin_b{};
    ghostrigger::native::core::math::transform_math::Vec3 direction_b{};
    if (!read_vec3(origin_a_xyz, origin_a) || !read_vec3(direction_a_xyz, direction_a) ||
        !read_vec3(origin_b_xyz, origin_b) || !read_vec3(direction_b_xyz, direction_b)) {
        return 0;
    }
    const auto [closest_a, closest_b] = ghostrigger::native::core::math::transform_math::closest_point_between_rays(
        origin_a,
        direction_a,
        origin_b,
        direction_b
    );
    if (write_vec3(closest_a, out_point_a_xyz) == 0) {
        return 0;
    }
    if (write_vec3(closest_b, out_point_b_xyz) == 0) {
        return 0;
    }
    return 1;
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_transform_screen_space_distance(
    double ax,
    double ay,
    double bx,
    double by
) {
    return ghostrigger::native::core::math::transform_math::screen_space_distance(ax, ay, bx, by);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_transform_rotation_angle_from_mouse_delta(
    double start_x,
    double start_y,
    double x,
    double y,
    double center_x,
    double center_y,
    int has_center
) {
    return ghostrigger::native::core::math::transform_math::rotation_angle_from_mouse_delta(
        start_x,
        start_y,
        x,
        y,
        center_x,
        center_y,
        has_center != 0
    );
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_axis_quaternion(
    char axis,
    double angle,
    double* out_xyzw
) {
    return write_quat(ghostrigger::native::core::math::transform_math::axis_quaternion(axis, angle), out_xyzw);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_multiply_quaternions(
    const double* a_xyzw,
    const double* b_xyzw,
    double* out_xyzw
) {
    ghostrigger::native::core::math::transform_math::Quat a{};
    ghostrigger::native::core::math::transform_math::Quat b{};
    if (!read_quat(a_xyzw, a) || !read_quat(b_xyzw, b)) {
        return 0;
    }
    return write_quat(ghostrigger::native::core::math::transform_math::multiply_quaternions(a, b), out_xyzw);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_rotate_vector(
    const double* rotation_xyzw,
    const double* vector_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::transform_math::Quat rotation{};
    ghostrigger::native::core::math::transform_math::Vec3 vector{};
    if (!read_quat(rotation_xyzw, rotation) || !read_vec3(vector_xyz, vector)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::transform_math::rotate_vector(rotation, vector), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_translation_matrix(
    const double* delta_xyz,
    double* out_matrix
) {
    ghostrigger::native::core::math::transform_math::Vec3 delta{};
    if (!read_vec3(delta_xyz, delta)) {
        return 0;
    }
    return write_matrix(ghostrigger::native::core::math::transform_math::build_translation_matrix(delta), out_matrix);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_rotation_matrix(
    char axis,
    double angle,
    double* out_matrix
) {
    return write_matrix(ghostrigger::native::core::math::transform_math::build_rotation_matrix(axis, angle), out_matrix);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_scale_matrix_scalar(
    double scale,
    double* out_matrix
) {
    return write_matrix(ghostrigger::native::core::math::transform_math::build_scale_matrix_scalar(scale), out_matrix);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_build_scale_matrix_vector(
    const double* scale_xyz,
    double* out_matrix
) {
    ghostrigger::native::core::math::transform_math::Vec3 scale{};
    if (!read_vec3(scale_xyz, scale)) {
        return 0;
    }
    return write_matrix(ghostrigger::native::core::math::transform_math::build_scale_matrix_vector(scale), out_matrix);
}

}
