#pragma once

namespace ghostrigger::core::converters::normal_map::math {

struct Vec2 {
    double x;
    double y;
};

struct Vec3 {
    double x;
    double y;
    double z;
};

struct Barycentric {
    double b0;
    double b1;
    double b2;
    bool valid;
};

struct TangentBasis {
    Vec3 tangent;
    Vec3 bitangent;
};

struct RayTriangleHit {
    double t;
    Barycentric barycentric;
    bool hit;
};

Vec3 normalize3(Vec3 value) noexcept;
double dot3(Vec3 lhs, Vec3 rhs) noexcept;
Vec3 cross3(Vec3 lhs, Vec3 rhs) noexcept;
Vec3 lerp3(Vec3 v0, Vec3 v1, Vec3 v2, Barycentric barycentric) noexcept;
Barycentric barycentric_uv(double u, double v, Vec2 uv0, Vec2 uv1, Vec2 uv2) noexcept;
TangentBasis compute_tangent(Vec3 v0, Vec3 v1, Vec3 v2, Vec2 uv0, Vec2 uv1, Vec2 uv2) noexcept;
Vec3 world_to_tangent(Vec3 world_n, Vec3 surface_n, Vec3 tangent, Vec3 bitangent) noexcept;
RayTriangleHit ray_triangle_intersect(Vec3 origin, Vec3 direction, Vec3 v0, Vec3 v1, Vec3 v2) noexcept;
const char* normal_map_math_contracts_schema_json() noexcept;

} // namespace ghostrigger::core::converters::normal_map::math
