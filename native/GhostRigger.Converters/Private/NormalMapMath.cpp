#include "NormalMapMath.h"

#include <cmath>

namespace ghostrigger::converters::normal_map::math {

Vec3 normalize3(Vec3 value) noexcept {
    const double length = std::sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
    if (length < 1.0e-8) {
        return {0.0, 0.0, 1.0};
    }
    return {value.x / length, value.y / length, value.z / length};
}

double dot3(Vec3 lhs, Vec3 rhs) noexcept {
    return lhs.x * rhs.x + lhs.y * rhs.y + lhs.z * rhs.z;
}

Vec3 cross3(Vec3 lhs, Vec3 rhs) noexcept {
    return {
        lhs.y * rhs.z - lhs.z * rhs.y,
        lhs.z * rhs.x - lhs.x * rhs.z,
        lhs.x * rhs.y - lhs.y * rhs.x,
    };
}

Vec3 lerp3(Vec3 v0, Vec3 v1, Vec3 v2, Barycentric barycentric) noexcept {
    return {
        v0.x * barycentric.b0 + v1.x * barycentric.b1 + v2.x * barycentric.b2,
        v0.y * barycentric.b0 + v1.y * barycentric.b1 + v2.y * barycentric.b2,
        v0.z * barycentric.b0 + v1.z * barycentric.b1 + v2.z * barycentric.b2,
    };
}

Barycentric barycentric_uv(double u, double v, Vec2 uv0, Vec2 uv1, Vec2 uv2) noexcept {
    const Vec2 v0 = {uv1.x - uv0.x, uv1.y - uv0.y};
    const Vec2 v1 = {uv2.x - uv0.x, uv2.y - uv0.y};
    const Vec2 v2 = {u - uv0.x, v - uv0.y};
    const double d00 = v0.x * v0.x + v0.y * v0.y;
    const double d01 = v0.x * v1.x + v0.y * v1.y;
    const double d11 = v1.x * v1.x + v1.y * v1.y;
    const double d20 = v2.x * v0.x + v2.y * v0.y;
    const double d21 = v2.x * v1.x + v2.y * v1.y;
    const double denominator = d00 * d11 - d01 * d01;
    if (std::abs(denominator) < 1.0e-10) {
        return {0.0, 0.0, 0.0, false};
    }

    const double b1 = (d11 * d20 - d01 * d21) / denominator;
    const double b2 = (d00 * d21 - d01 * d20) / denominator;
    const double b0 = 1.0 - b1 - b2;
    if (b0 < -0.001 || b1 < -0.001 || b2 < -0.001) {
        return {b0, b1, b2, false};
    }
    return {b0, b1, b2, true};
}

TangentBasis compute_tangent(Vec3 v0, Vec3 v1, Vec3 v2, Vec2 uv0, Vec2 uv1, Vec2 uv2) noexcept {
    const Vec3 e1 = {v1.x - v0.x, v1.y - v0.y, v1.z - v0.z};
    const Vec3 e2 = {v2.x - v0.x, v2.y - v0.y, v2.z - v0.z};
    const Vec2 d1 = {uv1.x - uv0.x, uv1.y - uv0.y};
    const Vec2 d2 = {uv2.x - uv0.x, uv2.y - uv0.y};
    const double denominator = d1.x * d2.y - d2.x * d1.y;
    if (std::abs(denominator) < 1.0e-10) {
        return {{1.0, 0.0, 0.0}, {0.0, 1.0, 0.0}};
    }

    const double reciprocal = 1.0 / denominator;
    const Vec3 tangent = {
        (d2.y * e1.x - d1.y * e2.x) * reciprocal,
        (d2.y * e1.y - d1.y * e2.y) * reciprocal,
        (d2.y * e1.z - d1.y * e2.z) * reciprocal,
    };
    const Vec3 bitangent = {
        (d1.x * e2.x - d2.x * e1.x) * reciprocal,
        (d1.x * e2.y - d2.x * e1.y) * reciprocal,
        (d1.x * e2.z - d2.x * e1.z) * reciprocal,
    };
    return {normalize3(tangent), normalize3(bitangent)};
}

Vec3 world_to_tangent(Vec3 world_n, Vec3 surface_n, Vec3 tangent, Vec3 bitangent) noexcept {
    return normalize3({dot3(world_n, tangent), dot3(world_n, bitangent), dot3(world_n, surface_n)});
}

RayTriangleHit ray_triangle_intersect(Vec3 origin, Vec3 direction, Vec3 v0, Vec3 v1, Vec3 v2) noexcept {
    constexpr double kEpsilon = 1.0e-7;
    const Vec3 e1 = {v1.x - v0.x, v1.y - v0.y, v1.z - v0.z};
    const Vec3 e2 = {v2.x - v0.x, v2.y - v0.y, v2.z - v0.z};
    const Vec3 h = cross3(direction, e2);
    const double a = dot3(e1, h);
    if (std::abs(a) < kEpsilon) {
        return {0.0, {0.0, 0.0, 0.0, false}, false};
    }

    const double f = 1.0 / a;
    const Vec3 s = {origin.x - v0.x, origin.y - v0.y, origin.z - v0.z};
    const double u = f * dot3(s, h);
    if (u < 0.0 || u > 1.0) {
        return {0.0, {0.0, 0.0, 0.0, false}, false};
    }

    const Vec3 q = cross3(s, e1);
    const double v = f * dot3(direction, q);
    if (v < 0.0 || u + v > 1.0) {
        return {0.0, {0.0, 0.0, 0.0, false}, false};
    }

    const double t = f * dot3(e2, q);
    if (t < kEpsilon) {
        return {0.0, {0.0, 0.0, 0.0, false}, false};
    }
    return {t, {1.0 - u - v, u, v, true}, true};
}

const char* normal_map_math_contracts_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"converters_normal_map_math_native.v1",)"
        R"("source":"src/converters/normal_map.py",)"
        R"("native_scope":["vector normalization","dot and cross products","barycentric UV solve","tangent basis solve","world-to-tangent normal conversion","ray triangle intersection"],)"
        R"("python_fallback":["TXIBuilder file output","SoftwareNormalBaker image writes","TGA/TPC conversion","external mesh converter imports","Blender FBX bridge"],)"
        R"("reason_python_fallback":"file IO, image baking loops, external converter runtime integration, and Blender/FBX bridge behavior remain Python-owned until ported as dedicated converter subsystems"})";
    return kJson;
}

} // namespace ghostrigger::converters::normal_map::math

extern "C" {

__declspec(dllexport) void gr_converters_normal_map_normalize3(
    double x,
    double y,
    double z,
    double* out_x,
    double* out_y,
    double* out_z
) {
    const auto result = ghostrigger::converters::normal_map::math::normalize3({x, y, z});
    if (out_x != nullptr) {
        *out_x = result.x;
    }
    if (out_y != nullptr) {
        *out_y = result.y;
    }
    if (out_z != nullptr) {
        *out_z = result.z;
    }
}

__declspec(dllexport) double gr_converters_normal_map_dot3(
    double ax,
    double ay,
    double az,
    double bx,
    double by,
    double bz
) {
    return ghostrigger::converters::normal_map::math::dot3({ax, ay, az}, {bx, by, bz});
}

__declspec(dllexport) int gr_converters_normal_map_barycentric_uv(
    double u,
    double v,
    double uv0_x,
    double uv0_y,
    double uv1_x,
    double uv1_y,
    double uv2_x,
    double uv2_y,
    double* out_b0,
    double* out_b1,
    double* out_b2
) {
    const auto result = ghostrigger::converters::normal_map::math::barycentric_uv(
        u,
        v,
        {uv0_x, uv0_y},
        {uv1_x, uv1_y},
        {uv2_x, uv2_y}
    );
    if (out_b0 != nullptr) {
        *out_b0 = result.b0;
    }
    if (out_b1 != nullptr) {
        *out_b1 = result.b1;
    }
    if (out_b2 != nullptr) {
        *out_b2 = result.b2;
    }
    return result.valid ? 1 : 0;
}

__declspec(dllexport) void gr_converters_normal_map_compute_tangent(
    double v0_x,
    double v0_y,
    double v0_z,
    double v1_x,
    double v1_y,
    double v1_z,
    double v2_x,
    double v2_y,
    double v2_z,
    double uv0_x,
    double uv0_y,
    double uv1_x,
    double uv1_y,
    double uv2_x,
    double uv2_y,
    double* tangent_x,
    double* tangent_y,
    double* tangent_z,
    double* bitangent_x,
    double* bitangent_y,
    double* bitangent_z
) {
    const auto result = ghostrigger::converters::normal_map::math::compute_tangent(
        {v0_x, v0_y, v0_z},
        {v1_x, v1_y, v1_z},
        {v2_x, v2_y, v2_z},
        {uv0_x, uv0_y},
        {uv1_x, uv1_y},
        {uv2_x, uv2_y}
    );
    if (tangent_x != nullptr) {
        *tangent_x = result.tangent.x;
    }
    if (tangent_y != nullptr) {
        *tangent_y = result.tangent.y;
    }
    if (tangent_z != nullptr) {
        *tangent_z = result.tangent.z;
    }
    if (bitangent_x != nullptr) {
        *bitangent_x = result.bitangent.x;
    }
    if (bitangent_y != nullptr) {
        *bitangent_y = result.bitangent.y;
    }
    if (bitangent_z != nullptr) {
        *bitangent_z = result.bitangent.z;
    }
}

__declspec(dllexport) void gr_converters_normal_map_world_to_tangent(
    double world_x,
    double world_y,
    double world_z,
    double surface_x,
    double surface_y,
    double surface_z,
    double tangent_x,
    double tangent_y,
    double tangent_z,
    double bitangent_x,
    double bitangent_y,
    double bitangent_z,
    double* out_x,
    double* out_y,
    double* out_z
) {
    const auto result = ghostrigger::converters::normal_map::math::world_to_tangent(
        {world_x, world_y, world_z},
        {surface_x, surface_y, surface_z},
        {tangent_x, tangent_y, tangent_z},
        {bitangent_x, bitangent_y, bitangent_z}
    );
    if (out_x != nullptr) {
        *out_x = result.x;
    }
    if (out_y != nullptr) {
        *out_y = result.y;
    }
    if (out_z != nullptr) {
        *out_z = result.z;
    }
}

__declspec(dllexport) int gr_converters_normal_map_ray_triangle_intersect(
    double origin_x,
    double origin_y,
    double origin_z,
    double direction_x,
    double direction_y,
    double direction_z,
    double v0_x,
    double v0_y,
    double v0_z,
    double v1_x,
    double v1_y,
    double v1_z,
    double v2_x,
    double v2_y,
    double v2_z,
    double* out_t,
    double* out_b0,
    double* out_b1,
    double* out_b2
) {
    const auto result = ghostrigger::converters::normal_map::math::ray_triangle_intersect(
        {origin_x, origin_y, origin_z},
        {direction_x, direction_y, direction_z},
        {v0_x, v0_y, v0_z},
        {v1_x, v1_y, v1_z},
        {v2_x, v2_y, v2_z}
    );
    if (out_t != nullptr) {
        *out_t = result.t;
    }
    if (out_b0 != nullptr) {
        *out_b0 = result.barycentric.b0;
    }
    if (out_b1 != nullptr) {
        *out_b1 = result.barycentric.b1;
    }
    if (out_b2 != nullptr) {
        *out_b2 = result.barycentric.b2;
    }
    return result.hit ? 1 : 0;
}

__declspec(dllexport) const char* gr_converters_normal_map_math_contracts_schema_json() {
    return ghostrigger::converters::normal_map::math::normal_map_math_contracts_schema_json();
}

}
