#pragma once

#ifdef GHOSTRIGGER_MEASUREMENT_EXPORTS
#define GHOSTRIGGER_MEASUREMENT_API __declspec(dllexport)
#else
#define GHOSTRIGGER_MEASUREMENT_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_version();
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_capabilities_json();
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_owner_boundary_json();
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_dependency_schema_json();
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_normalize_unit(const char* unit_name, const char* fallback);
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_unit_symbol(const char* unit_name);
GHOSTRIGGER_MEASUREMENT_API double gr_measurement_convert_distance(double value, const char* from_unit, const char* to_unit);
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_format_distance(double value, const char* system_unit, const char* display_unit, int precision);
GHOSTRIGGER_MEASUREMENT_API int gr_measurement_parse_distance(const char* text, const char* system_unit, const char* display_unit, double* out_value);
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_format_angle_degrees(double value, int precision);
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_format_scale(double value);
GHOSTRIGGER_MEASUREMENT_API double gr_measurement_snap_degrees(int enabled, double angle, double increment_degrees);
GHOSTRIGGER_MEASUREMENT_API double gr_measurement_snap_radians(int enabled, double angle, double increment_degrees);
GHOSTRIGGER_MEASUREMENT_API double gr_measurement_snap_percent(int enabled, double value, double increment_percent);
GHOSTRIGGER_MEASUREMENT_API double gr_measurement_snap_scale_factor(int enabled, double scale_factor, double increment_percent);
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_contracts_schema_json();
}
