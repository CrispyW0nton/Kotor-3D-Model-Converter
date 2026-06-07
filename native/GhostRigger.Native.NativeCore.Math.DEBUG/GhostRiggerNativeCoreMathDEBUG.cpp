#include "GhostRiggerNativeCoreMath.h"

#include <cmath>
#include <cstring>
#include <iostream>

namespace {

bool near_value(float actual, float expected) {
    return std::fabs(actual - expected) < 0.0001f;
}

} // namespace

int main()
{
    const char* version = gr_native_core_math_version();
    if (std::strcmp(version, "0.1.0") != 0) {
        std::cerr << "Unexpected GhostRigger.Native.NativeCore.Math version" << std::endl;
        return 1;
    }

    const char* capabilities = gr_native_core_math_capabilities_json();
    if (std::strstr(capabilities, R"("bounds_helpers":true)") == nullptr ||
        std::strstr(capabilities, R"("matrix_helpers":true)") == nullptr) {
        std::cerr << "GhostRigger.Native.NativeCore.Math capabilities missing expected flags" << std::endl;
        return 2;
    }

    const float points[] = {
        -1.0f, 2.0f, 5.0f,
        3.0f, -4.0f, 6.0f,
        2.0f, 8.0f, -7.0f,
    };
    float min_xyz[3] = {};
    float max_xyz[3] = {};
    if (!gr_native_core_math_bounds_from_points(points, 3, min_xyz, max_xyz)) {
        std::cerr << "GhostRigger.Native.NativeCore.Math failed to compute bounds" << std::endl;
        return 3;
    }
    if (!near_value(min_xyz[0], -1.0f) || !near_value(min_xyz[1], -4.0f) || !near_value(min_xyz[2], -7.0f) ||
        !near_value(max_xyz[0], 3.0f) || !near_value(max_xyz[1], 8.0f) || !near_value(max_xyz[2], 6.0f)) {
        std::cerr << "GhostRigger.Native.NativeCore.Math bounds output mismatch" << std::endl;
        return 4;
    }

    float center_xyz[3] = {};
    if (!gr_native_core_math_bounds_center(min_xyz, max_xyz, center_xyz) ||
        !near_value(center_xyz[0], 1.0f) || !near_value(center_xyz[1], 2.0f) || !near_value(center_xyz[2], -0.5f)) {
        std::cerr << "GhostRigger.Native.NativeCore.Math center output mismatch" << std::endl;
        return 5;
    }

    const float matrix[] = {
        1.0f, 0.0f, 0.0f, 10.0f,
        0.0f, 1.0f, 0.0f, -2.0f,
        0.0f, 0.0f, 1.0f, 3.5f,
        0.0f, 0.0f, 0.0f, 1.0f,
    };
    const float point[] = {1.0f, 2.0f, 3.0f};
    float transformed[3] = {};
    if (!gr_native_core_math_transform_point(matrix, point, transformed) ||
        !near_value(transformed[0], 11.0f) || !near_value(transformed[1], 0.0f) ||
        !near_value(transformed[2], 6.5f)) {
        std::cerr << "GhostRigger.Native.NativeCore.Math transform output mismatch" << std::endl;
        return 6;
    }

    std::cout << "GhostRigger.Native.NativeCore.Math.DEBUG OK: " << version << std::endl;
    return 0;
}
