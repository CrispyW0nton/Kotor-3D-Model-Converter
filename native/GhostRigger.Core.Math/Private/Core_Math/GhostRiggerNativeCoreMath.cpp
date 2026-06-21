#include "../../GhostRigger.Native.Core.Foundation/Public/GhostRiggerPythonPayloadResource.h"
#include "Core_Math/GhostRiggerNativeCoreMath.h"

#include <algorithm>
#include <limits>

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kCapabilities =
    R"({"name":"GhostRigger.Native.Core.Foundation","version":"0.1.0",)"
    R"("phase":"P1 foundation","bounds_helpers":true,"matrix_helpers":true,)"
    R"("camera_math_native":true,"camera_math_schema":"camera_math.v1",)"
    R"("frame_math_native":true,"frame_math_schema":"frame_math.v1",)"
    R"("gpu_math_native":true,"gpu_math_schema":"gpu_math.v1",)"
    R"("module_layout_math_native":true,"module_layout_math_schema":"module_layout_math.v1",)"
    R"("transform_math_native":true,"transform_math_schema":"transform_math.v1",)"
    R"("viewcube_math_native":true,"viewcube_math_schema":"viewcube_math.v1",)"
    R"("python_fallback_secondary":true,"renderer_neutral":true})";

bool valid_vec3(float* xyz) {
    return xyz != nullptr;
}

bool valid_vec3_const(const float* xyz) {
    return xyz != nullptr;
}

} // namespace

extern "C" {

GR_NATIVE_CORE_MATH_API const char* gr_native_core_math_version() {
    return kVersion;
}

GR_NATIVE_CORE_MATH_API const char* gr_native_core_math_capabilities_json() {
    return kCapabilities;
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_bounds_from_points(
    const float* xyz_points,
    std::uint32_t point_count,
    float* out_min_xyz,
    float* out_max_xyz) {
    if (xyz_points == nullptr || point_count == 0 || !valid_vec3(out_min_xyz) || !valid_vec3(out_max_xyz)) {
        return 0;
    }

    float min_xyz[3] = {
        std::numeric_limits<float>::max(),
        std::numeric_limits<float>::max(),
        std::numeric_limits<float>::max(),
    };
    float max_xyz[3] = {
        std::numeric_limits<float>::lowest(),
        std::numeric_limits<float>::lowest(),
        std::numeric_limits<float>::lowest(),
    };

    for (std::uint32_t index = 0; index < point_count; ++index) {
        const float* point = xyz_points + (index * 3);
        for (int axis = 0; axis < 3; ++axis) {
            min_xyz[axis] = std::min(min_xyz[axis], point[axis]);
            max_xyz[axis] = std::max(max_xyz[axis], point[axis]);
        }
    }

    for (int axis = 0; axis < 3; ++axis) {
        out_min_xyz[axis] = min_xyz[axis];
        out_max_xyz[axis] = max_xyz[axis];
    }
    return 1;
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_bounds_center(
    const float* min_xyz,
    const float* max_xyz,
    float* out_center_xyz) {
    if (!valid_vec3_const(min_xyz) || !valid_vec3_const(max_xyz) || !valid_vec3(out_center_xyz)) {
        return 0;
    }

    for (int axis = 0; axis < 3; ++axis) {
        out_center_xyz[axis] = (min_xyz[axis] + max_xyz[axis]) * 0.5f;
    }
    return 1;
}

GR_NATIVE_CORE_MATH_API int gr_native_core_math_transform_point(
    const float* matrix4x4_row_major,
    const float* point_xyz,
    float* out_xyz) {
    if (matrix4x4_row_major == nullptr || !valid_vec3_const(point_xyz) || !valid_vec3(out_xyz)) {
        return 0;
    }

    const float x = point_xyz[0];
    const float y = point_xyz[1];
    const float z = point_xyz[2];
    out_xyz[0] = matrix4x4_row_major[0] * x + matrix4x4_row_major[1] * y +
        matrix4x4_row_major[2] * z + matrix4x4_row_major[3];
    out_xyz[1] = matrix4x4_row_major[4] * x + matrix4x4_row_major[5] * y +
        matrix4x4_row_major[6] * z + matrix4x4_row_major[7];
    out_xyz[2] = matrix4x4_row_major[8] * x + matrix4x4_row_major[9] * y +
        matrix4x4_row_major[10] * z + matrix4x4_row_major[11];
    return 1;
}

}

