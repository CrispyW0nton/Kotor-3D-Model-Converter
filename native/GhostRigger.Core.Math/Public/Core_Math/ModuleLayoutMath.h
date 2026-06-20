#pragma once

#include "Core_Math/GhostRiggerNativeCoreMath.h"

namespace ghostrigger::native::core::math::module_layout_math {

struct Vec3 {
    double x;
    double y;
    double z;
};

Vec3 module_anchor_relative_position(
    Vec3 room_lyt_position,
    Vec3 anchor_lyt_position,
    Vec3 anchor_scene_position
);

} // namespace ghostrigger::native::core::math::module_layout_math

extern "C" {

GR_NATIVE_CORE_MATH_API int gr_native_core_math_module_anchor_relative_position(
    const double* room_lyt_xyz,
    const double* anchor_lyt_xyz,
    const double* anchor_scene_xyz,
    double* out_xyz);

}
