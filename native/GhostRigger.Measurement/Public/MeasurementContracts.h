#pragma once

namespace ghostrigger::measurement::core::measurement::contracts {

const char* normalize_unit(const char* unit_name, const char* fallback) noexcept;
const char* unit_symbol(const char* unit_name) noexcept;
double convert_distance(double value, const char* from_unit, const char* to_unit) noexcept;
const char* format_distance(double value_in_system_units, const char* system_unit, const char* display_unit, int precision) noexcept;
int parse_distance(const char* text, const char* system_unit, const char* display_unit, double* out_value) noexcept;
const char* format_angle_degrees(double value, int precision) noexcept;
const char* format_scale(double value) noexcept;
double clamp_angle_increment(double value) noexcept;
double snap_degrees(int enabled, double angle, double increment_degrees) noexcept;
double snap_radians(int enabled, double angle, double increment_degrees) noexcept;
double clamp_percent_increment(double value) noexcept;
double snap_percent(int enabled, double value, double increment_percent) noexcept;
double snap_scale_factor(int enabled, double scale_factor, double increment_percent) noexcept;
const char* measurement_contracts_schema_json() noexcept;

} // namespace ghostrigger::measurement::core::measurement::contracts
