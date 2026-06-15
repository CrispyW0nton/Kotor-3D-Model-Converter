#pragma once

#include "GhostRiggerAnimationRetargeting.h"

#include <cstddef>
#include <string>
#include <vector>

namespace ghostrigger::domain::core::animationretargeting::core::animation_retargeting::retargeter {

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

std::vector<std::string> candidate_names(const std::string& source_name);
Vec3 sub3(Vec3 a, Vec3 b);
Vec3 add3(Vec3 a, Vec3 b, double scale);
Vec3 mul3(Vec3 a, double scale);
Quat normal_quat(Quat q);
Quat quat_conjugate(Quat q);
Quat quat_mul(Quat a, Quat b);
Quat retarget_rotation(Quat src_pose_rot, Quat src_bind_rot, Quat dst_bind_rot);
double height_from_positions(const double* xyz_values, std::size_t point_count);

} // namespace ghostrigger::domain::core::animationretargeting::core::animation_retargeting::retargeter

extern "C" {

GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_candidate_names_json(
    const char* source_name
);

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_sub3(
    const double* a_xyz,
    const double* b_xyz,
    double* out_xyz
);

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_add3(
    const double* a_xyz,
    const double* b_xyz,
    double scale,
    double* out_xyz
);

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_mul3(
    const double* a_xyz,
    double scale,
    double* out_xyz
);

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_normal_quat(
    const double* q_xyzw,
    double* out_xyzw
);

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_quat_conjugate(
    const double* q_xyzw,
    double* out_xyzw
);

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_quat_mul(
    const double* a_xyzw,
    const double* b_xyzw,
    double* out_xyzw
);

GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_retarget_rotation(
    const double* src_pose_xyzw,
    const double* src_bind_xyzw,
    const double* dst_bind_xyzw,
    double* out_xyzw
);

GHOSTRIGGER_ANIMATION_RETARGETING_API double gr_animation_retargeting_height_from_positions(
    const double* xyz_values,
    std::size_t point_count
);

}
