#pragma once

#ifdef GHOSTRIGGER_SCENE_EXPORTS
#define GHOSTRIGGER_SCENE_API __declspec(dllexport)
#else
#define GHOSTRIGGER_SCENE_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_SCENE_API const char* gr_scene_version();
GHOSTRIGGER_SCENE_API const char* gr_scene_capabilities_json();
GHOSTRIGGER_SCENE_API const char* gr_scene_owner_boundary_json();
GHOSTRIGGER_SCENE_API const char* gr_scene_dependency_schema_json();
GHOSTRIGGER_SCENE_API const char* gr_scene_normalize_axis_mode(const char* mode);
GHOSTRIGGER_SCENE_API const char* gr_scene_axis_mode_label(const char* mode);
GHOSTRIGGER_SCENE_API const char* gr_scene_axis_mode_values_json();
GHOSTRIGGER_SCENE_API int gr_scene_identity_basis(double* output_basis9);
GHOSTRIGGER_SCENE_API int gr_scene_finite_basis(const double* basis9, double* output_basis9);
GHOSTRIGGER_SCENE_API int gr_scene_quat_to_basis(const double* quat4, double* output_basis9);
GHOSTRIGGER_SCENE_API const char* gr_scene_axis_mode_contracts_schema_json();
GHOSTRIGGER_SCENE_API int gr_scene_sanitize_vec3(const double* values3, const double* fallback3, double* output3);
GHOSTRIGGER_SCENE_API int gr_scene_transform_defaults(double* position3, double* rotation3, double* scale3);
GHOSTRIGGER_SCENE_API int gr_scene_pivot_defaults(double* position3, double* rotation3, int* enabled);
GHOSTRIGGER_SCENE_API int gr_scene_pivot_values_are_valid(const double* position3, const double* rotation3);
GHOSTRIGGER_SCENE_API const char* gr_scene_sanitize_resource_game(const char* game);
GHOSTRIGGER_SCENE_API const char* gr_scene_resource_ref_defaults_json();
GHOSTRIGGER_SCENE_API int gr_scene_metadata_key_is_persisted(const char* key);
GHOSTRIGGER_SCENE_API const char* gr_scene_primitives_schema_json();
}
