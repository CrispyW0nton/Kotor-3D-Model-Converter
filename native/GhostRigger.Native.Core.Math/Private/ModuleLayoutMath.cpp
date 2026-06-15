#include "ModuleLayoutMath.h"

namespace ghostrigger::native::core::math::module_layout_math {

Vec3 module_anchor_relative_position(
    Vec3 room_lyt_position,
    Vec3 anchor_lyt_position,
    Vec3 anchor_scene_position
) {
    return {
        anchor_scene_position.x + (room_lyt_position.x - anchor_lyt_position.x),
        anchor_scene_position.y + (room_lyt_position.y - anchor_lyt_position.y),
        anchor_scene_position.z + (room_lyt_position.z - anchor_lyt_position.z),
    };
}

} // namespace ghostrigger::native::core::math::module_layout_math

namespace {

bool read_vec3(
    const double* value,
    ghostrigger::native::core::math::module_layout_math::Vec3& out_value
) {
    if (value == nullptr) {
        return false;
    }
    out_value = {value[0], value[1], value[2]};
    return true;
}

int write_vec3(ghostrigger::native::core::math::module_layout_math::Vec3 value, double* out_value) {
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

GR_NATIVE_CORE_MATH_API int gr_native_core_math_module_anchor_relative_position(
    const double* room_lyt_xyz,
    const double* anchor_lyt_xyz,
    const double* anchor_scene_xyz,
    double* out_xyz
) {
    ghostrigger::native::core::math::module_layout_math::Vec3 room{};
    ghostrigger::native::core::math::module_layout_math::Vec3 anchor_lyt{};
    ghostrigger::native::core::math::module_layout_math::Vec3 anchor_scene{};
    if (!read_vec3(room_lyt_xyz, room) || !read_vec3(anchor_lyt_xyz, anchor_lyt) || !read_vec3(anchor_scene_xyz, anchor_scene)) {
        return 0;
    }
    return write_vec3(
        ghostrigger::native::core::math::module_layout_math::module_anchor_relative_position(
            room,
            anchor_lyt,
            anchor_scene
        ),
        out_xyz
    );
}

}
