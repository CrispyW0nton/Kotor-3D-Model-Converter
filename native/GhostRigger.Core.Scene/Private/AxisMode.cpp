#include "AxisMode.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cctype>
#include <string>

namespace ghostrigger::core::scene::core::scene::axis_mode {
namespace {

std::string normalized_key(std::string_view value) {
    std::size_t start = 0;
    std::size_t end = value.size();
    while (start < end && std::isspace(static_cast<unsigned char>(value[start]))) {
        ++start;
    }
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }

    std::string result;
    result.reserve(end - start);
    for (std::size_t index = start; index < end; ++index) {
        const unsigned char character = static_cast<unsigned char>(value[index]);
        if (character == '-' || character == ' ') {
            result.push_back('_');
        } else {
            result.push_back(static_cast<char>(std::tolower(character)));
        }
    }
    return result;
}

bool is_finite_matrix(const Matrix3& basis) noexcept {
    return std::all_of(basis.begin(), basis.end(), [](double value) {
        return std::isfinite(value);
    });
}

} // namespace

AxisMode normalize_axis_mode(std::string_view value) noexcept {
    const std::string key = normalized_key(value);
    if (key == "view") {
        return AxisMode::View;
    }
    if (key == "screen") {
        return AxisMode::Screen;
    }
    if (key == "parent") {
        return AxisMode::Parent;
    }
    if (key == "local") {
        return AxisMode::Local;
    }
    if (key == "gimbal") {
        return AxisMode::Gimbal;
    }
    if (key == "grid") {
        return AxisMode::Grid;
    }
    if (key == "working") {
        return AxisMode::Working;
    }
    if (key == "pick") {
        return AxisMode::Pick;
    }
    return AxisMode::World;
}

const char* axis_mode_to_string(AxisMode mode) noexcept {
    switch (mode) {
    case AxisMode::View:
        return "view";
    case AxisMode::Screen:
        return "screen";
    case AxisMode::World:
        return "world";
    case AxisMode::Parent:
        return "parent";
    case AxisMode::Local:
        return "local";
    case AxisMode::Gimbal:
        return "gimbal";
    case AxisMode::Grid:
        return "grid";
    case AxisMode::Working:
        return "working";
    case AxisMode::Pick:
        return "pick";
    default:
        return "world";
    }
}

const char* axis_mode_label(AxisMode mode) noexcept {
    switch (mode) {
    case AxisMode::View:
        return "View";
    case AxisMode::Screen:
        return "Screen";
    case AxisMode::World:
        return "World";
    case AxisMode::Parent:
        return "Parent";
    case AxisMode::Local:
        return "Local";
    case AxisMode::Gimbal:
        return "Gimbal";
    case AxisMode::Grid:
        return "Grid";
    case AxisMode::Working:
        return "Working";
    case AxisMode::Pick:
        return "Pick";
    default:
        return "World";
    }
}

const char* axis_mode_values_json() noexcept {
    static constexpr const char* kJson =
        R"(["view","screen","world","parent","local","gimbal","grid","working","pick"])";
    return kJson;
}

Matrix3 identity_basis() noexcept {
    return {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
}

Matrix3 finite_basis(const double* basis9) noexcept {
    if (basis9 == nullptr) {
        return identity_basis();
    }
    Matrix3 basis{};
    for (std::size_t index = 0; index < basis.size(); ++index) {
        basis[index] = basis9[index];
    }
    return is_finite_matrix(basis) ? basis : identity_basis();
}

Vec3 normalize_vector(Vec3 value, Vec3 fallback) noexcept {
    const double length = std::sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]);
    if (length > 1.0e-9 && std::isfinite(length)) {
        return {value[0] / length, value[1] / length, value[2] / length};
    }
    return fallback;
}

Matrix3 quat_to_basis(const double* quat4) noexcept {
    Quat quat = {0.0, 0.0, 0.0, 1.0};
    if (quat4 != nullptr) {
        quat = {quat4[0], quat4[1], quat4[2], quat4[3]};
    }

    const double length = std::sqrt(
        quat[0] * quat[0] + quat[1] * quat[1] + quat[2] * quat[2] + quat[3] * quat[3]
    );
    if (length <= 1.0e-9 || !std::isfinite(length)) {
        return identity_basis();
    }

    const double x = quat[0] / length;
    const double y = quat[1] / length;
    const double z = quat[2] / length;
    const double w = quat[3] / length;
    return {
        1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + z * w), 2.0 * (x * z - y * w),
        2.0 * (x * y - z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z + x * w),
        2.0 * (x * z + y * w), 2.0 * (y * z - x * w), 1.0 - 2.0 * (x * x + y * y),
    };
}

const char* axis_mode_contracts_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"axis_mode_native.v1",)"
        R"("source":"src/core/scene/axis_mode.py",)"
        R"("native_scope":["AxisMode normalization","AxisMode labels","AxisMode value list","identity basis","finite basis validation","vector normalization","quaternion to basis conversion"],)"
        R"("python_fallback":["TransformReferenceController object ownership","selected object and parent lookup","camera view matrix lookup","pick reference scene deletion checks","dynamic Python object attributes"],)"
        R"("reason_python_fallback":"controller behavior still depends on Python scene, camera, and object references until those runtime structures are ported"})";
    return kJson;
}

} // namespace ghostrigger::core::scene::core::scene::axis_mode
