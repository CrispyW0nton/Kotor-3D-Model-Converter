#include "ViewcubeMath.h"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <cstring>
#include <limits>
#include <numbers>

namespace ghostrigger::native::core::math::viewcube_math {
namespace {

constexpr double kEpsilon = 1.0e-9;

void set_xyz(Vec3 value, double* out_xyz) {
    if (out_xyz != nullptr) {
        out_xyz[0] = value.x;
        out_xyz[1] = value.y;
        out_xyz[2] = value.z;
    }
}

void set_quat(Quat value, double* out_quat) {
    if (out_quat != nullptr) {
        out_quat[0] = value.x;
        out_quat[1] = value.y;
        out_quat[2] = value.z;
        out_quat[3] = value.w;
    }
}

} // namespace

Vec3 normalize(Vec3 v) {
    const double length = std::sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
    if (length <= kEpsilon) {
        return {0.0, 1.0, 0.0};
    }
    return {v.x / length, v.y / length, v.z / length};
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

void azimuth_elevation_from_direction(Vec3 direction, double* out_azimuth_degrees, double* out_elevation_degrees) {
    const Vec3 normalized = normalize(direction);
    if (out_azimuth_degrees == nullptr || out_elevation_degrees == nullptr) {
        return;
    }
    const double azimuth = std::fmod(std::atan2(normalized.y, normalized.x) * 180.0 / std::numbers::pi + 360.0, 360.0);
    double elevation = std::asin(std::clamp(normalized.z, -1.0, 1.0)) * 180.0 / std::numbers::pi;
    if (elevation > 85.0) {
        elevation = 85.0;
    } else if (elevation < -85.0) {
        elevation = -85.0;
    }
    *out_azimuth_degrees = azimuth;
    *out_elevation_degrees = elevation;
}

ViewAction action_from_view_name(const char* view_name) {
    if (view_name == nullptr) {
        return ViewAction::kInvalid;
    }
    char buffer[17] = {};
    std::size_t i = 0;
    while (i < sizeof(buffer) - 1 && view_name[i] != '\0') {
        buffer[i] = static_cast<char>(std::tolower(static_cast<unsigned char>(view_name[i])));
        ++i;
    }
    buffer[i] = '\0';

    if (std::strcmp(buffer, "f") == 0 || std::strcmp(buffer, "front") == 0) {
        return ViewAction::kFront;
    }
    if (std::strcmp(buffer, "b") == 0 || std::strcmp(buffer, "back") == 0) {
        return ViewAction::kBack;
    }
    if (std::strcmp(buffer, "l") == 0 || std::strcmp(buffer, "left") == 0) {
        return ViewAction::kLeft;
    }
    if (std::strcmp(buffer, "r") == 0 || std::strcmp(buffer, "right") == 0) {
        return ViewAction::kRight;
    }
    if (std::strcmp(buffer, "t") == 0 || std::strcmp(buffer, "top") == 0) {
        return ViewAction::kTop;
    }
    if (std::strcmp(buffer, "bo") == 0 || std::strcmp(buffer, "bottom") == 0) {
        return ViewAction::kBottom;
    }
    if (std::strcmp(buffer, "persp") == 0 || std::strcmp(buffer, "perspective") == 0) {
        return ViewAction::kPerspective;
    }
    if (std::strcmp(buffer, "home") == 0) {
        return ViewAction::kHome;
    }
    return ViewAction::kInvalid;
}

bool target_for_action(ViewAction action, double* out_azimuth_degrees, double* out_elevation_degrees) {
    static const double kFront[2] = {90.0, 0.0};
    static const double kBack[2] = {270.0, 0.0};
    static const double kLeft[2] = {180.0, 0.0};
    static const double kRight[2] = {0.0, 0.0};
    static const double kTop[2] = {90.0, 85.0};
    static const double kBottom[2] = {90.0, -85.0};
    if (out_azimuth_degrees == nullptr || out_elevation_degrees == nullptr) {
        return false;
    }
    switch (action) {
    case ViewAction::kFront:
        *out_azimuth_degrees = kFront[0];
        *out_elevation_degrees = kFront[1];
        return true;
    case ViewAction::kBack:
        *out_azimuth_degrees = kBack[0];
        *out_elevation_degrees = kBack[1];
        return true;
    case ViewAction::kLeft:
        *out_azimuth_degrees = kLeft[0];
        *out_elevation_degrees = kLeft[1];
        return true;
    case ViewAction::kRight:
        *out_azimuth_degrees = kRight[0];
        *out_elevation_degrees = kRight[1];
        return true;
    case ViewAction::kTop:
        *out_azimuth_degrees = kTop[0];
        *out_elevation_degrees = kTop[1];
        return true;
    case ViewAction::kBottom:
        *out_azimuth_degrees = kBottom[0];
        *out_elevation_degrees = kBottom[1];
        return true;
    default:
        return false;
    }
}

void view_direction_from_angles(double azimuth, double elevation, double* out_x, double* out_y, double* out_z) {
    if (out_x == nullptr || out_y == nullptr || out_z == nullptr) {
        return;
    }
    const double azimuth_radians = azimuth * std::numbers::pi / 180.0;
    const double elevation_radians = elevation * std::numbers::pi / 180.0;
    const double cos_elevation = std::cos(elevation_radians);
    const Vec3 result {
        cos_elevation * std::cos(azimuth_radians),
        cos_elevation * std::sin(azimuth_radians),
        std::sin(elevation_radians),
    };
    const Vec3 normalized = normalize(result);
    *out_x = normalized.x;
    *out_y = normalized.y;
    *out_z = normalized.z;
}

void camera_basis_from_angles(double azimuth, double elevation, double* out_right_xyz, double* out_up_xyz, double* out_forward_xyz) {
    double direction_x = 0.0;
    double direction_y = 0.0;
    double direction_z = 0.0;
    view_direction_from_angles(azimuth, elevation, &direction_x, &direction_y, &direction_z);
    const Vec3 eye_direction = {direction_x, direction_y, direction_z};
    const Vec3 forward = {-eye_direction.x, -eye_direction.y, -eye_direction.z};
    Vec3 right = normalize(cross(forward, {0.0, 0.0, 1.0}));
    if (dot(right, right) < 1.0e-6) {
        right = normalize(cross(forward, {0.0, 1.0, 0.0}));
    }
    const Vec3 up = cross(right, forward);
    set_xyz(right, out_right_xyz);
    set_xyz(up, out_up_xyz);
    set_xyz(forward, out_forward_xyz);
}

Quat view_orientation_quaternion(double azimuth, double elevation) {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    view_direction_from_angles(azimuth, elevation, &x, &y, &z);
    const Vec3 base = {0.0, 1.0, 0.0};
    const Vec3 target = {x, y, z};
    const double d = std::clamp(dot(base, target), -1.0, 1.0);
    if (d > 0.999999) {
        return {0.0, 0.0, 0.0, 1.0};
    }
    if (d < -0.999999) {
        return {0.0, 0.0, 1.0, 0.0};
    }
    const Vec3 cross_axis = cross(base, target);
    const Quat quat = {cross_axis.x, cross_axis.y, cross_axis.z, 1.0 + d};
    const double len = std::sqrt(quat.x * quat.x + quat.y * quat.y + quat.z * quat.z + quat.w * quat.w);
    return {quat.x / len, quat.y / len, quat.z / len, quat.w / len};
}

} // namespace ghostrigger::native::core::math::viewcube_math

namespace {

bool read_vec3(const double* source, ghostrigger::native::core::math::viewcube_math::Vec3& out_value) {
    if (source == nullptr) {
        return false;
    }
    out_value = {source[0], source[1], source[2]};
    return true;
}

int write_vec3(const ghostrigger::native::core::math::viewcube_math::Vec3& value, double* out_value) {
    if (out_value == nullptr) {
        return 0;
    }
    out_value[0] = value.x;
    out_value[1] = value.y;
    out_value[2] = value.z;
    return 1;
}

int write_quat(const ghostrigger::native::core::math::viewcube_math::Quat& value, double* out_value) {
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

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_normalize(
    const double* value_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::viewcube_math::Vec3 value{};
    if (!read_vec3(value_xyz, value)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::viewcube_math::normalize(value), out_xyz);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_cross(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::viewcube_math::Vec3 a{};
    ghostrigger::native::core::math::viewcube_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0;
    }
    return write_vec3(ghostrigger::native::core::math::viewcube_math::cross(a, b), out_xyz);
}

GR_NATIVE_CORE_MATH_API double gr_native_core_math_viewcube_dot(
    const double* a_xyz,
    const double* b_xyz
) {
    ghostrigger::native::core::math::viewcube_math::Vec3 a{};
    ghostrigger::native::core::math::viewcube_math::Vec3 b{};
    if (!read_vec3(a_xyz, a) || !read_vec3(b_xyz, b)) {
        return 0.0;
    }
    return ghostrigger::native::core::math::viewcube_math::dot(a, b);
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_azimuth_elevation_from_direction(
    const double* direction_xyz,
    double* out_azimuth_degrees,
    double* out_elevation_degrees
) {
    ghostrigger::native::core::math::viewcube_math::Vec3 direction{};
    if (!read_vec3(direction_xyz, direction)) {
        return 0;
    }
    ghostrigger::native::core::math::viewcube_math::azimuth_elevation_from_direction(
        direction,
        out_azimuth_degrees,
        out_elevation_degrees
    );
    return 1;
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_action_from_view_name(
    const char* view_name,
    int* out_action
) {
    const auto action = ghostrigger::native::core::math::viewcube_math::action_from_view_name(view_name);
    if (out_action == nullptr) {
        return 0;
    }
    *out_action = static_cast<int>(action);
    return action == ghostrigger::native::core::math::viewcube_math::ViewAction::kInvalid ? 0 : 1;
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_target_for_action(
    int action,
    double* out_azimuth_degrees,
    double* out_elevation_degrees
) {
    if (out_azimuth_degrees == nullptr || out_elevation_degrees == nullptr) {
        return 0;
    }
    auto mapped = static_cast<ghostrigger::native::core::math::viewcube_math::ViewAction>(action);
    if (mapped == ghostrigger::native::core::math::viewcube_math::ViewAction::kPerspective ||
        mapped == ghostrigger::native::core::math::viewcube_math::ViewAction::kHome ||
        mapped == ghostrigger::native::core::math::viewcube_math::ViewAction::kInvalid) {
        return 0;
    }
    return ghostrigger::native::core::math::viewcube_math::target_for_action(
        mapped,
        out_azimuth_degrees,
        out_elevation_degrees
    ) ? 1 : 0;
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_view_direction_from_angles(
    double azimuth,
    double elevation,
    double* out_xyz
) {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    ghostrigger::native::core::math::viewcube_math::view_direction_from_angles(azimuth, elevation, &x, &y, &z);
    if (out_xyz == nullptr) {
        return 0;
    }
    out_xyz[0] = x;
    out_xyz[1] = y;
    out_xyz[2] = z;
    return 1;
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_camera_basis_from_angles(
    double azimuth,
    double elevation,
    double* out_right_xyz,
    double* out_up_xyz,
    double* out_forward_xyz
) {
    ghostrigger::native::core::math::viewcube_math::camera_basis_from_angles(
        azimuth,
        elevation,
        out_right_xyz,
        out_up_xyz,
        out_forward_xyz
    );
    if (out_right_xyz == nullptr || out_up_xyz == nullptr || out_forward_xyz == nullptr) {
        return 0;
    }
    return 1;
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_view_orientation_quaternion(
    double azimuth,
    double elevation,
    double* out_xyzw
) {
    return write_quat(ghostrigger::native::core::math::viewcube_math::view_orientation_quaternion(azimuth, elevation), out_xyzw);
}

}
