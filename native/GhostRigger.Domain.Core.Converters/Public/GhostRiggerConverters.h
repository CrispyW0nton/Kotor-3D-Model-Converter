#pragma once

#ifdef GHOSTRIGGER_CONVERTERS_EXPORTS
#define GHOSTRIGGER_CONVERTERS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CONVERTERS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_version();
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_capabilities_json();
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_owner_boundary_json();
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_dependency_schema_json();
GHOSTRIGGER_CONVERTERS_API void gr_converters_normal_map_normalize3(
    double x,
    double y,
    double z,
    double* out_x,
    double* out_y,
    double* out_z
);
GHOSTRIGGER_CONVERTERS_API double gr_converters_normal_map_dot3(
    double ax,
    double ay,
    double az,
    double bx,
    double by,
    double bz
);
GHOSTRIGGER_CONVERTERS_API int gr_converters_normal_map_barycentric_uv(
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
);
GHOSTRIGGER_CONVERTERS_API void gr_converters_normal_map_compute_tangent(
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
);
GHOSTRIGGER_CONVERTERS_API void gr_converters_normal_map_world_to_tangent(
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
);
GHOSTRIGGER_CONVERTERS_API int gr_converters_normal_map_ray_triangle_intersect(
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
);
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_normal_map_math_contracts_schema_json();
}
