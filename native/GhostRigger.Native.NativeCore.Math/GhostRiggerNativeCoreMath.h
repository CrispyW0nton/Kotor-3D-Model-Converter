#pragma once

#include <cstdint>

#if defined(_WIN32)
#if defined(NATIVE_CORE_MATH_EXPORTS)
#define GR_NATIVE_CORE_MATH_API __declspec(dllexport)
#else
#define GR_NATIVE_CORE_MATH_API __declspec(dllimport)
#endif
#else
#define GR_NATIVE_CORE_MATH_API
#endif

extern "C" {

GR_NATIVE_CORE_MATH_API const char* gr_native_core_math_version();
GR_NATIVE_CORE_MATH_API const char* gr_native_core_math_capabilities_json();
GR_NATIVE_CORE_MATH_API int gr_native_core_math_bounds_from_points(
    const float* xyz_points,
    std::uint32_t point_count,
    float* out_min_xyz,
    float* out_max_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_bounds_center(
    const float* min_xyz,
    const float* max_xyz,
    float* out_center_xyz);
GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_point(
    const float* matrix4x4_row_major,
    const float* point_xyz,
    float* out_xyz);

}
