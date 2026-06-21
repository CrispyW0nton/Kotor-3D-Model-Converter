#pragma once

#include "Core_Math/GhostRiggerNativeCoreMath.h"

namespace ghostrigger::native::core::math::viewcube_math {

enum class ViewAction {
    kFront = 0,
    kBack = 1,
    kLeft = 2,
    kRight = 3,
    kTop = 4,
    kBottom = 5,
    kPerspective = 6,
    kHome = 7,
    kInvalid = 255,
};

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

Vec3 normalize(Vec3 v);
Vec3 cross(Vec3 a, Vec3 b);
double dot(Vec3 a, Vec3 b);
void azimuth_elevation_from_direction(Vec3 direction, double* out_azimuth_degrees, double* out_elevation_degrees);
ViewAction action_from_view_name(const char* view_name);
bool target_for_action(ViewAction action, double* out_azimuth_degrees, double* out_elevation_degrees);
void view_direction_from_angles(double azimuth, double elevation, double* out_x, double* out_y, double* out_z);
void camera_basis_from_angles(double azimuth, double elevation, double* out_right_xyz, double* out_up_xyz, double* out_forward_xyz);
Quat view_orientation_quaternion(double azimuth, double elevation);

} // namespace ghostrigger::native::core::math::viewcube_math

extern "C" {

GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_normalize(
    const double* value_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_cross(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API double gr_native_core_math_viewcube_dot(
    const double* a_xyz,
    const double* b_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_azimuth_elevation_from_direction(
    const double* direction_xyz,
    double* out_azimuth_degrees,
    double* out_elevation_degrees
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_action_from_view_name(
    const char* view_name,
    int* out_action
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_target_for_action(
    int action,
    double* out_azimuth_degrees,
    double* out_elevation_degrees
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_view_direction_from_angles(
    double azimuth,
    double elevation,
    double* out_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_camera_basis_from_angles(
    double azimuth,
    double elevation,
    double* out_right_xyz,
    double* out_up_xyz,
    double* out_forward_xyz
);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_viewcube_view_orientation_quaternion(
    double azimuth,
    double elevation,
    double* out_xyzw
);

}
