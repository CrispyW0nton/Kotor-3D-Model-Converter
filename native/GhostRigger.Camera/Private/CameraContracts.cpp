#include "CameraContracts.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <string>
#include <string_view>

namespace ghostrigger::camera::core::camera::contracts {
namespace {

constexpr double kPi = 3.141592653589793238462643383279502884;

struct SensorPreset {
    const char* name;
    double width;
    double height;
    const char* json;
};

struct LensPreset {
    const char* name;
    double focal_length_mm;
};

constexpr std::array<const char*, 4> kCameraTypes = {
    "Free Camera",
    "Target Camera",
    "Cinematic Camera",
    "Orthographic Camera",
};

constexpr std::array<SensorPreset, 6> kSensorPresets = {{
    {"16mm Film", 10.26, 7.49, R"({"name":"16mm Film","width_mm":10.26,"height_mm":7.49})"},
    {"35mm Academy", 21.95, 16.00, R"({"name":"35mm Academy","width_mm":21.95,"height_mm":16.0})"},
    {"Super 35", 24.89, 18.66, R"({"name":"Super 35","width_mm":24.89,"height_mm":18.66})"},
    {"Full Frame 36x24", 36.00, 24.00, R"({"name":"Full Frame 36x24","width_mm":36.0,"height_mm":24.0})"},
    {"IMAX Approx", 70.00, 48.50, R"({"name":"IMAX Approx","width_mm":70.0,"height_mm":48.5})"},
    {"Digital Cinema", 27.03, 14.25, R"({"name":"Digital Cinema","width_mm":27.03,"height_mm":14.25})"},
}};

constexpr std::array<LensPreset, 6> kLensPresets = {{
    {"18mm Wide", 18.0},
    {"24mm Wide", 24.0},
    {"35mm Standard", 35.0},
    {"50mm Normal", 50.0},
    {"85mm Portrait", 85.0},
    {"135mm Telephoto", 135.0},
}};

std::string trim(std::string value) {
    const auto first = std::find_if_not(value.begin(), value.end(), [](unsigned char ch) { return std::isspace(ch) != 0; });
    const auto last = std::find_if_not(value.rbegin(), value.rend(), [](unsigned char ch) { return std::isspace(ch) != 0; }).base();
    if (first >= last) {
        return {};
    }
    return std::string(first, last);
}

std::string upper_trim(const char* text) {
    std::string value = trim(text == nullptr ? std::string() : std::string(text));
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) { return static_cast<char>(std::toupper(ch)); });
    return value;
}

std::string_view text_or_empty(const char* text) noexcept {
    return text == nullptr ? std::string_view() : std::string_view(text);
}

} // namespace

double clamp(double value, double low, double high) noexcept {
    return std::max(low, std::min(high, value));
}

double focal_length_to_fov(double sensor_width_mm, double focal_length_mm) noexcept {
    const double sensor = std::max(0.001, sensor_width_mm);
    const double focal = std::max(0.001, focal_length_mm);
    return 180.0 / kPi * (2.0 * std::atan(sensor / (2.0 * focal)));
}

double fov_to_focal_length(double sensor_width_mm, double fov_degrees) noexcept {
    const double sensor = std::max(0.001, sensor_width_mm);
    const double fov = clamp(fov_degrees, 1.0, 179.0) * kPi / 180.0;
    return sensor / (2.0 * std::tan(fov * 0.5));
}

void normalize_quat(double x, double y, double z, double w, double* out_xyzw) noexcept {
    if (out_xyzw == nullptr) {
        return;
    }
    const double n = std::sqrt(x * x + y * y + z * z + w * w);
    if (n <= 1.0e-9 || !std::isfinite(n)) {
        out_xyzw[0] = 0.0;
        out_xyzw[1] = 0.0;
        out_xyzw[2] = 0.0;
        out_xyzw[3] = 1.0;
        return;
    }
    out_xyzw[0] = x / n;
    out_xyzw[1] = y / n;
    out_xyzw[2] = z / n;
    out_xyzw[3] = w / n;
}

const char* normalize_camera_type(const char* camera_type) noexcept {
    const std::string_view value = text_or_empty(camera_type);
    for (const char* row : kCameraTypes) {
        if (value == row) {
            return row;
        }
    }
    return "Cinematic Camera";
}

const char* normalize_render_format(const char* output_format) noexcept {
    const std::string fmt = upper_trim(output_format);
    if (fmt == "JPG" || fmt == "JPEG" || fmt == "PNG" || fmt == "TGA") {
        return fmt == "JPEG" ? "JPEG" : (fmt == "JPG" ? "JPG" : (fmt == "TGA" ? "TGA" : "PNG"));
    }
    return "PNG";
}

const char* render_output_extension(const char* output_format) noexcept {
    const std::string fmt = upper_trim(normalize_render_format(output_format));
    if (fmt == "JPG" || fmt == "JPEG") {
        return "jpg";
    }
    if (fmt == "TGA") {
        return "tga";
    }
    return "png";
}

int validate_dimension(int value) noexcept {
    return std::max(1, value);
}

int validate_jpg_quality(int value) noexcept {
    return std::max(1, std::min(100, value));
}

const char* sanitize_filename(const char* name) noexcept {
    thread_local std::string clean;
    clean.clear();
    const std::string input = trim(name == nullptr ? std::string() : std::string(name));
    bool previous_invalid = false;
    for (unsigned char ch : input) {
        const bool valid = (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '_' || ch == '.' || ch == '-';
        if (valid) {
            clean.push_back(static_cast<char>(ch));
            previous_invalid = false;
        } else if (!previous_invalid) {
            clean.push_back('_');
            previous_invalid = true;
        } else {
            previous_invalid = true;
        }
    }
    while (!clean.empty() && (clean.front() == '.' || clean.front() == '_')) {
        clean.erase(clean.begin());
    }
    while (!clean.empty() && (clean.back() == '.' || clean.back() == '_')) {
        clean.pop_back();
    }
    if (clean.empty()) {
        clean = "render";
    }
    return clean.c_str();
}

const char* sensor_preset_json(const char* name) noexcept {
    const std::string_view value = text_or_empty(name);
    for (const auto& preset : kSensorPresets) {
        if (value == preset.name) {
            return preset.json;
        }
    }
    return R"({"name":"","width_mm":36.0,"height_mm":24.0})";
}

double lens_preset_mm(const char* name, double fallback) noexcept {
    const std::string_view value = text_or_empty(name);
    for (const auto& preset : kLensPresets) {
        if (value == preset.name) {
            return preset.focal_length_mm;
        }
    }
    return fallback;
}

const char* camera_contracts_schema_json() noexcept {
    return R"({"schema":"camera_contracts_native.v1",)"
           R"("source":["src/core/camera/camera_model.py","src/core/camera/camera_render_settings.py","src/core/camera/render_output.py","src/core/camera/camera_presets.py","src/math/camera_math.py"],)"
           R"("native_scope":["focal length/FOV conversion","quaternion normalization","camera type normalization","render format normalization","resolution and JPG quality clamping","render filename sanitation","sensor preset lookup","lens preset lookup"],)"
           R"("python_fallback":["image save/encoding","render manifest file writes","camera manager object lifetime","viewport adapter state","Qt workflow orchestration"],)"
           R"("reason_python_fallback":"Image encoding, manifest persistence, live camera object ownership, viewport adapter state, and Qt workflow orchestration depend on Python runtime objects and should be ported as dedicated subsystem slices"})";
}

} // namespace ghostrigger::camera::core::camera::contracts

extern "C" {

__declspec(dllexport) double gr_camera_focal_length_to_fov(double sensor_width_mm, double focal_length_mm) {
    return ghostrigger::camera::core::camera::contracts::focal_length_to_fov(sensor_width_mm, focal_length_mm);
}

__declspec(dllexport) double gr_camera_fov_to_focal_length(double sensor_width_mm, double fov_degrees) {
    return ghostrigger::camera::core::camera::contracts::fov_to_focal_length(sensor_width_mm, fov_degrees);
}

__declspec(dllexport) void gr_camera_normalize_quat(double x, double y, double z, double w, double* out_xyzw) {
    ghostrigger::camera::core::camera::contracts::normalize_quat(x, y, z, w, out_xyzw);
}

__declspec(dllexport) const char* gr_camera_normalize_type(const char* camera_type) {
    return ghostrigger::camera::core::camera::contracts::normalize_camera_type(camera_type);
}

__declspec(dllexport) const char* gr_camera_normalize_render_format(const char* output_format) {
    return ghostrigger::camera::core::camera::contracts::normalize_render_format(output_format);
}

__declspec(dllexport) const char* gr_camera_render_output_extension(const char* output_format) {
    return ghostrigger::camera::core::camera::contracts::render_output_extension(output_format);
}

__declspec(dllexport) int gr_camera_validate_dimension(int value) {
    return ghostrigger::camera::core::camera::contracts::validate_dimension(value);
}

__declspec(dllexport) int gr_camera_validate_jpg_quality(int value) {
    return ghostrigger::camera::core::camera::contracts::validate_jpg_quality(value);
}

__declspec(dllexport) const char* gr_camera_sanitize_filename(const char* name) {
    return ghostrigger::camera::core::camera::contracts::sanitize_filename(name);
}

__declspec(dllexport) const char* gr_camera_sensor_preset_json(const char* name) {
    return ghostrigger::camera::core::camera::contracts::sensor_preset_json(name);
}

__declspec(dllexport) double gr_camera_lens_preset_mm(const char* name, double fallback) {
    return ghostrigger::camera::core::camera::contracts::lens_preset_mm(name, fallback);
}

__declspec(dllexport) const char* gr_camera_contracts_schema_json() {
    return ghostrigger::camera::core::camera::contracts::camera_contracts_schema_json();
}

}
