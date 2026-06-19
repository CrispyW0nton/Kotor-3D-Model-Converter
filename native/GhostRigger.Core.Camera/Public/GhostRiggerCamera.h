#pragma once

#ifdef GHOSTRIGGER_CAMERA_EXPORTS
#define GHOSTRIGGER_CAMERA_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CAMERA_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CAMERA_API const char* gr_camera_version();
GHOSTRIGGER_CAMERA_API const char* gr_camera_capabilities_json();
GHOSTRIGGER_CAMERA_API const char* gr_camera_owner_boundary_json();
GHOSTRIGGER_CAMERA_API const char* gr_camera_dependency_schema_json();
GHOSTRIGGER_CAMERA_API double gr_camera_focal_length_to_fov(double sensor_width_mm, double focal_length_mm);
GHOSTRIGGER_CAMERA_API double gr_camera_fov_to_focal_length(double sensor_width_mm, double fov_degrees);
GHOSTRIGGER_CAMERA_API void gr_camera_normalize_quat(double x, double y, double z, double w, double* out_xyzw);
GHOSTRIGGER_CAMERA_API const char* gr_camera_normalize_type(const char* camera_type);
GHOSTRIGGER_CAMERA_API const char* gr_camera_normalize_render_format(const char* output_format);
GHOSTRIGGER_CAMERA_API const char* gr_camera_render_output_extension(const char* output_format);
GHOSTRIGGER_CAMERA_API int gr_camera_validate_dimension(int value);
GHOSTRIGGER_CAMERA_API int gr_camera_validate_jpg_quality(int value);
GHOSTRIGGER_CAMERA_API const char* gr_camera_sanitize_filename(const char* name);
GHOSTRIGGER_CAMERA_API const char* gr_camera_sensor_preset_json(const char* name);
GHOSTRIGGER_CAMERA_API double gr_camera_lens_preset_mm(const char* name, double fallback);
GHOSTRIGGER_CAMERA_API const char* gr_camera_contracts_schema_json();
}
