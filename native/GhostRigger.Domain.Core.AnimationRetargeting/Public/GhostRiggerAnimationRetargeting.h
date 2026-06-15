#pragma once

#ifdef GHOSTRIGGER_ANIMATION_RETARGETING_EXPORTS
#define GHOSTRIGGER_ANIMATION_RETARGETING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ANIMATION_RETARGETING_API __declspec(dllimport)
#endif

#include <cstddef>

extern "C" {
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_version();
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_capabilities_json();
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_owner_boundary_json();
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_dependency_schema_json();
GHOSTRIGGER_ANIMATION_RETARGETING_API const char* gr_animation_retargeting_candidate_names_json(const char* source_name);
GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_sub3(const double* a_xyz, const double* b_xyz, double* out_xyz);
GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_add3(const double* a_xyz, const double* b_xyz, double scale, double* out_xyz);
GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_mul3(const double* a_xyz, double scale, double* out_xyz);
GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_normal_quat(const double* q_xyzw, double* out_xyzw);
GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_quat_conjugate(const double* q_xyzw, double* out_xyzw);
GHOSTRIGGER_ANIMATION_RETARGETING_API int gr_animation_retargeting_quat_mul(const double* a_xyzw, const double* b_xyzw, double* out_xyzw);
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
