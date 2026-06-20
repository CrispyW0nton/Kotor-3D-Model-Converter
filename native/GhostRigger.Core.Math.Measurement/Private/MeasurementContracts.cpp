#include "MeasurementContracts.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>
#include <string_view>

namespace ghostrigger::core::measurement::core::measurement::contracts {
namespace {

struct UnitRow {
    const char* canonical;
    const char* symbol;
    double centimeters;
};

constexpr UnitRow kUnits[] = {
    {"millimetres", "mm", 0.1},
    {"centimetres", "cm", 1.0},
    {"metres", "m", 100.0},
    {"kilometres", "km", 100000.0},
    {"inches", "in", 2.54},
    {"feet", "ft", 30.48},
    {"yards", "yd", 91.44},
};

struct AliasRow {
    const char* alias;
    const char* canonical;
};

constexpr AliasRow kAliases[] = {
    {"millimeters", "millimetres"}, {"millimeter", "millimetres"}, {"millimetre", "millimetres"}, {"mm", "millimetres"},
    {"centimeters", "centimetres"}, {"centimeter", "centimetres"}, {"centimetre", "centimetres"}, {"cm", "centimetres"},
    {"meters", "metres"}, {"meter", "metres"}, {"metre", "metres"}, {"m", "metres"},
    {"kilometers", "kilometres"}, {"kilometer", "kilometres"}, {"kilometre", "kilometres"}, {"km", "kilometres"},
    {"inch", "inches"}, {"in", "inches"},
    {"foot", "feet"}, {"ft", "feet"},
    {"yard", "yards"}, {"yd", "yards"},
};

std::string lower_trim(const char* text) {
    std::string value = text == nullptr ? std::string() : std::string(text);
    const auto first = std::find_if_not(value.begin(), value.end(), [](unsigned char ch) { return std::isspace(ch) != 0; });
    const auto last = std::find_if_not(value.rbegin(), value.rend(), [](unsigned char ch) { return std::isspace(ch) != 0; }).base();
    if (first >= last) {
        return {};
    }
    std::string result(first, last);
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return result;
}

const UnitRow* unit_row(std::string_view canonical) noexcept {
    for (const auto& row : kUnits) {
        if (canonical == row.canonical) {
            return &row;
        }
    }
    return nullptr;
}

std::string fixed_trim(double value, int precision, bool fix_negative_zero) {
    precision = std::clamp(precision, 0, 6);
    if (precision == 0) {
        const auto rounded = static_cast<long long>(std::nearbyint(value));
        return std::to_string(rounded);
    }
    std::ostringstream stream;
    stream << std::fixed << std::setprecision(precision) << value;
    std::string text = stream.str();
    while (!text.empty() && text.back() == '0') {
        text.pop_back();
    }
    if (!text.empty() && text.back() == '.') {
        text.pop_back();
    }
    if (fix_negative_zero && text == "-0") {
        return "0";
    }
    return text;
}

double centimeters_per_unit(const char* unit_name) noexcept {
    const auto* row = unit_row(normalize_unit(unit_name, "centimetres"));
    return row == nullptr ? 1.0 : row->centimeters;
}

} // namespace

const char* normalize_unit(const char* unit_name, const char* fallback) noexcept {
    const std::string key = lower_trim(unit_name);
    for (const auto& row : kUnits) {
        if (key == row.canonical) {
            return row.canonical;
        }
    }
    for (const auto& alias : kAliases) {
        if (key == alias.alias) {
            return alias.canonical;
        }
    }
    return fallback == nullptr ? "centimetres" : fallback;
}

const char* unit_symbol(const char* unit_name) noexcept {
    const auto* row = unit_row(normalize_unit(unit_name, "centimetres"));
    return row == nullptr ? normalize_unit(unit_name, "centimetres") : row->symbol;
}

double convert_distance(double value, const char* from_unit, const char* to_unit) noexcept {
    const double value_cm = value * centimeters_per_unit(from_unit);
    return value_cm / centimeters_per_unit(to_unit);
}

const char* format_distance(double value_in_system_units, const char* system_unit, const char* display_unit, int precision) noexcept {
    thread_local std::string text;
    const char* sys = normalize_unit(system_unit, "centimetres");
    const char* display = normalize_unit(display_unit, sys);
    const double value = convert_distance(value_in_system_units, sys, display);
    text = fixed_trim(value, std::clamp(precision, 0, 6), true);
    text += " ";
    text += unit_symbol(display);
    return text.c_str();
}

int parse_distance(const char* text, const char* system_unit, const char* display_unit, double* out_value) noexcept {
    if (out_value == nullptr || text == nullptr) {
        return 0;
    }
    const std::string trimmed = lower_trim(text);
    if (trimmed.empty()) {
        return 0;
    }
    char* end = nullptr;
    const double value = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str() || !std::isfinite(value)) {
        return 0;
    }
    while (*end != '\0' && std::isspace(static_cast<unsigned char>(*end)) != 0) {
        ++end;
    }
    const std::string suffix(end);
    if (suffix.empty()) {
        const char* sys = normalize_unit(system_unit, "centimetres");
        const char* display = normalize_unit(display_unit, sys);
        *out_value = convert_distance(value, display, sys);
        return 1;
    }
    if (std::any_of(suffix.begin(), suffix.end(), [](unsigned char ch) { return std::isalpha(ch) == 0; })) {
        return 0;
    }
    const char* unit = normalize_unit(suffix.c_str(), "");
    if (unit[0] == '\0') {
        return 0;
    }
    *out_value = convert_distance(value, unit, normalize_unit(system_unit, "centimetres"));
    return 1;
}

const char* format_angle_degrees(double value, int precision) noexcept {
    thread_local std::string text;
    text = fixed_trim(value, std::clamp(precision, 0, 4), false);
    text += " deg";
    return text.c_str();
}

const char* format_scale(double value) noexcept {
    thread_local std::string text;
    if (!std::isfinite(value)) {
        return "unavailable";
    }
    text = fixed_trim(value, 3, false);
    return text.c_str();
}

double clamp_angle_increment(double value) noexcept {
    return std::max(1.0e-6, std::min(value, 360.0));
}

double snap_degrees(int enabled, double angle, double increment_degrees) noexcept {
    if (enabled == 0) {
        return angle;
    }
    const double inc = clamp_angle_increment(increment_degrees);
    return std::nearbyint(angle / inc) * inc;
}

double snap_radians(int enabled, double angle, double increment_degrees) noexcept {
    if (enabled == 0) {
        return angle;
    }
    constexpr double kPi = 3.141592653589793238462643383279502884;
    return snap_degrees(1, angle * 180.0 / kPi, increment_degrees) * kPi / 180.0;
}

double clamp_percent_increment(double value) noexcept {
    if (!std::isfinite(value)) {
        value = 10.0;
    }
    return std::max(1.0e-6, std::min(value, 1000.0));
}

double snap_percent(int enabled, double value, double increment_percent) noexcept {
    if (enabled == 0) {
        return value;
    }
    const double inc = clamp_percent_increment(increment_percent);
    return std::nearbyint(value / inc) * inc;
}

double snap_scale_factor(int enabled, double scale_factor, double increment_percent) noexcept {
    const double floor = std::max(0.001, scale_factor);
    if (enabled == 0) {
        return floor;
    }
    return std::max(0.001, snap_percent(1, floor * 100.0, increment_percent) / 100.0);
}

const char* measurement_contracts_schema_json() noexcept {
    return R"({"schema":"measurement_contracts_native.v1",)"
           R"("source":["src/measurement/unit_system.py","src/measurement/measurement_formatter.py","src/measurement/angle_snap.py","src/measurement/percent_snap.py"],)"
           R"("native_scope":["unit normalization","unit symbols","distance conversion","distance formatting","distance parsing","angle formatting","scale formatting","angle snapping","percent snapping"],)"
           R"("python_fallback":["MeasurementSettings file IO","measurement overlay drawing","controller start/update/finish state","object dimension introspection","grid bounds calculation"],)"
           R"("reason_python_fallback":"Persistence, drawing, controller state, and runtime object inspection depend on app objects and UI/project boundaries that should be ported in dedicated subsystem slices"})";
}

} // namespace ghostrigger::core::measurement::core::measurement::contracts

extern "C" {

__declspec(dllexport) const char* gr_measurement_normalize_unit(const char* unit_name, const char* fallback) {
    return ghostrigger::core::measurement::core::measurement::contracts::normalize_unit(unit_name, fallback);
}

__declspec(dllexport) const char* gr_measurement_unit_symbol(const char* unit_name) {
    return ghostrigger::core::measurement::core::measurement::contracts::unit_symbol(unit_name);
}

__declspec(dllexport) double gr_measurement_convert_distance(double value, const char* from_unit, const char* to_unit) {
    return ghostrigger::core::measurement::core::measurement::contracts::convert_distance(value, from_unit, to_unit);
}

__declspec(dllexport) const char* gr_measurement_format_distance(double value, const char* system_unit, const char* display_unit, int precision) {
    return ghostrigger::core::measurement::core::measurement::contracts::format_distance(value, system_unit, display_unit, precision);
}

__declspec(dllexport) int gr_measurement_parse_distance(const char* text, const char* system_unit, const char* display_unit, double* out_value) {
    return ghostrigger::core::measurement::core::measurement::contracts::parse_distance(text, system_unit, display_unit, out_value);
}

__declspec(dllexport) const char* gr_measurement_format_angle_degrees(double value, int precision) {
    return ghostrigger::core::measurement::core::measurement::contracts::format_angle_degrees(value, precision);
}

__declspec(dllexport) const char* gr_measurement_format_scale(double value) {
    return ghostrigger::core::measurement::core::measurement::contracts::format_scale(value);
}

__declspec(dllexport) double gr_measurement_snap_degrees(int enabled, double angle, double increment_degrees) {
    return ghostrigger::core::measurement::core::measurement::contracts::snap_degrees(enabled, angle, increment_degrees);
}

__declspec(dllexport) double gr_measurement_snap_radians(int enabled, double angle, double increment_degrees) {
    return ghostrigger::core::measurement::core::measurement::contracts::snap_radians(enabled, angle, increment_degrees);
}

__declspec(dllexport) double gr_measurement_snap_percent(int enabled, double value, double increment_percent) {
    return ghostrigger::core::measurement::core::measurement::contracts::snap_percent(enabled, value, increment_percent);
}

__declspec(dllexport) double gr_measurement_snap_scale_factor(int enabled, double scale_factor, double increment_percent) {
    return ghostrigger::core::measurement::core::measurement::contracts::snap_scale_factor(enabled, scale_factor, increment_percent);
}

__declspec(dllexport) const char* gr_measurement_contracts_schema_json() {
    return ghostrigger::core::measurement::core::measurement::contracts::measurement_contracts_schema_json();
}

}
