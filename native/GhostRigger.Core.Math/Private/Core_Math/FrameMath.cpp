#include "Core_Math/FrameMath.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <sstream>

namespace ghostrigger::native::core::math::frame_math {
namespace {

constexpr double kEpsilon = 1.0e-9;

double length(Vec3 value) {
    return std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
}

} // namespace

Vec3 normalize(Vec3 value) {
    const double len = length(value);
    if (len > kEpsilon) {
        return {value.x / len, value.y / len, value.z / len};
    }
    return {0.0, 1.0, 0.0};
}

std::string clean_texture_name(const char* name) {
    if (name == nullptr || name[0] == '\0') {
        return "";
    }

    std::string output;
    for (const unsigned char* cursor = reinterpret_cast<const unsigned char*>(name); *cursor != '\0'; ++cursor) {
        if (*cursor >= 32 && *cursor <= 126) {
            output.push_back(static_cast<char>(*cursor));
        } else {
            break;
        }
    }

    const auto not_space = [](unsigned char value) {
        return std::isspace(value) == 0;
    };
    output.erase(output.begin(), std::find_if(output.begin(), output.end(), not_space));
    output.erase(std::find_if(output.rbegin(), output.rend(), not_space).base(), output.end());
    return output;
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

Vec3 sub(Vec3 a, Vec3 b) {
    return {a.x - b.x, a.y - b.y, a.z - b.z};
}

Vec3 add(Vec3 a, Vec3 b) {
    return {a.x + b.x, a.y + b.y, a.z + b.z};
}

double clamp(double value, double low, double high) {
    return std::max(low, std::min(high, value));
}

double lerp(double a, double b, double t) {
    return a + (b - a) * t;
}

double unwrap_uv(double base, double other) {
    double diff = other - base;
    while (diff > 0.5) {
        other -= 1.0;
        diff -= 1.0;
    }
    while (diff < -0.5) {
        other += 1.0;
        diff += 1.0;
    }
    return other;
}

bool edge_has_seam(double a, double b) {
    const double raw_dist = std::abs(b - a);
    const double b_wrapped = unwrap_uv(a, b);
    const double wrap_dist = std::abs(b_wrapped - a);
    return wrap_dist < raw_dist - 0.01;
}

double vflip_nontiled(double v, double texture_height) {
    return (1.0 - v) * texture_height;
}

double vflip_tiled(double v, double tile_v, double source_height) {
    return (tile_v - v) * source_height;
}

std::uint32_t float_to_sort_key(double value) {
    const float narrowed = static_cast<float>(value);
    std::uint32_t bits = 0;
    std::memcpy(&bits, &narrowed, sizeof(bits));
    const std::uint32_t mask = (static_cast<std::uint32_t>(-(static_cast<std::int32_t>(bits >> 31)))) | 0x80000000U;
    return bits ^ mask;
}

double compute_screen_size_ratio(
    Vec3 bounds_min,
    Vec3 bounds_max,
    Vec3 view_origin,
    double fov_vertical_rad,
    int viewport_height
) {
    if (viewport_height <= 0 || fov_vertical_rad <= 0.0) {
        return 1.0;
    }

    const double cx = (bounds_min.x + bounds_max.x) * 0.5;
    const double cy = (bounds_min.y + bounds_max.y) * 0.5;
    const double cz = (bounds_min.z + bounds_max.z) * 0.5;
    const double rx = bounds_max.x - cx;
    const double ry = bounds_max.y - cy;
    const double rz = bounds_max.z - cz;
    const double sphere_r = std::sqrt(rx * rx + ry * ry + rz * rz);
    const double dx = cx - view_origin.x;
    const double dy = cy - view_origin.y;
    const double dz = cz - view_origin.z;
    const double dist = std::sqrt(dx * dx + dy * dy + dz * dz);
    if (dist < 1.0e-6) {
        return 1.0;
    }

    const double tan_half_fov = std::tan(fov_vertical_rad * 0.5);
    if (tan_half_fov < kEpsilon) {
        return 1.0;
    }
    return sphere_r / (dist * tan_half_fov);
}

} // namespace ghostrigger::native::core::math::frame_math

namespace {

bool read_vec3(
    const double* value,
    ghostrigger::native::core::math::frame_math::Vec3& out_value
) {
    if (value == nullptr) {
        return false;
    }
    out_value = {value[0], value[1], value[2]};
    return true;
}

int write_vec3(ghostrigger::native::core::math::frame_math::Vec3 value, double* out_value) {
    if (out_value == nullptr) {
        return 0;
    }
    out_value[0] = value.x;
    out_value[1] = value.y;
    out_value[2] = value.z;
    return 1;
}

} // namespace

extern "C" {

GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_normalize_vec3(
    const double* value_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::frame_math::Vec3 value{};
    if (!read_vec3(value_xyz, value)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::frame_math::normalize(value), out_xyz);
}

GR_NATIVE_CORE_MATH_API const char* gr_native_core_math_frame_clean_texture_name(const char* name) {
    thread_local std::string output;
    output = ghostrigger::native::core::math::frame_math::clean_texture_name(name);
    return output.c_str();
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_cross(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::frame_math::Vec3 a{};
    ghostrigger::native::core::math::frame_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::frame_math::cross(a, b), out_xyz);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_dot(
    const double* a_xyz,
    const double* b_xyz
) {
    ghostrigger::native::core::math::frame_math::Vec3 a{};
    ghostrigger::native::core::math::frame_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0.0;
    }
    return ghostrigger::native::core::math::frame_math::dot(a, b);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_sub(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::frame_math::Vec3 a{};
    ghostrigger::native::core::math::frame_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::frame_math::sub(a, b), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_add(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::frame_math::Vec3 a{};
    ghostrigger::native::core::math::frame_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::frame_math::add(a, b), out_xyz);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_clamp(
    double value,
    double low,
    double high
) {
    return ghostrigger::native::core::math::frame_math::clamp(value, low, high);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_lerp(
    double a,
    double b,
    double t
) {
    return ghostrigger::native::core::math::frame_math::lerp(a, b, t);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_unwrap_uv(
    double base,
    double other
) {
    return ghostrigger::native::core::math::frame_math::unwrap_uv(base, other);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_frame_edge_has_seam(
    double a,
    double b
) {
    return ghostrigger::native::core::math::frame_math::edge_has_seam(a, b) ? 1 : 0;
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_vflip_nontiled(
    double v,
    double texture_height
) {
    return ghostrigger::native::core::math::frame_math::vflip_nontiled(v, texture_height);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_vflip_tiled(
    double v,
    double tile_v,
    double source_height
) {
    return ghostrigger::native::core::math::frame_math::vflip_tiled(v, tile_v, source_height);
}

GR_NATIVE_CORE_MATH_API std::uint32_t gr_native_core_math_frame_float_to_sort_key(double value) {
    return ghostrigger::native::core::math::frame_math::float_to_sort_key(value);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_frame_compute_screen_size_ratio(
    const double* bounds_min_xyz,
    const double* bounds_max_xyz,
    const double* view_origin_xyz,
    double fov_vertical_rad,
    int viewport_height
) {
    ghostrigger::native::core::math::frame_math::Vec3 bounds_min{};
    ghostrigger::native::core::math::frame_math::Vec3 bounds_max{};
    ghostrigger::native::core::math::frame_math::Vec3 view_origin{};
    if (!read_vec3(bounds_min_xyz, bounds_min) || !read_vec3(bounds_max_xyz, bounds_max) || !read_vec3(view_origin_xyz, view_origin)) {
        return 1.0;
    }
    return ghostrigger::native::core::math::frame_math::compute_screen_size_ratio(
        bounds_min,
        bounds_max,
        view_origin,
        fov_vertical_rad,
        viewport_height
    );
}

}
