#pragma once

namespace ghostrigger::core::camera::core::camera::contracts {

double clamp(double value, double low, double high) noexcept;
double focal_length_to_fov(double sensor_width_mm, double focal_length_mm) noexcept;
double fov_to_focal_length(double sensor_width_mm, double fov_degrees) noexcept;
void normalize_quat(double x, double y, double z, double w, double* out_xyzw) noexcept;
const char* normalize_camera_type(const char* camera_type) noexcept;
const char* normalize_render_format(const char* output_format) noexcept;
const char* render_output_extension(const char* output_format) noexcept;
int validate_dimension(int value) noexcept;
int validate_jpg_quality(int value) noexcept;
const char* sanitize_filename(const char* name) noexcept;
const char* sensor_preset_json(const char* name) noexcept;
double lens_preset_mm(const char* name, double fallback) noexcept;
const char* camera_contracts_schema_json() noexcept;

} // namespace ghostrigger::core::camera::core::camera::contracts
