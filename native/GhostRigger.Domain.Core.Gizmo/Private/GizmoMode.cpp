#include "GizmoMode.h"

#include <cctype>
#include <cmath>
#include <string>

namespace ghostrigger::domain::core::gizmo::core::gizmo::gizmo_mode {
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
        result.push_back(static_cast<char>(std::tolower(character)));
    }
    return result;
}

bool read_vec3(const double* values, double out[3]) noexcept {
    if (values == nullptr) {
        return false;
    }
    for (int index = 0; index < 3; ++index) {
        const double value = values[index];
        if (!std::isfinite(value)) {
            return false;
        }
        out[index] = value;
    }
    return true;
}

void write_vec3(const double values[3], double* out) noexcept {
    if (out == nullptr) {
        return;
    }
    out[0] = values[0];
    out[1] = values[1];
    out[2] = values[2];
}

} // namespace

GizmoMode normalize_gizmo_mode(std::string_view value) noexcept {
    const std::string key = normalized_key(value);
    if (key == "rotate") {
        return GizmoMode::Rotate;
    }
    if (key == "scale") {
        return GizmoMode::Scale;
    }
    return GizmoMode::Translate;
}

const char* gizmo_mode_to_string(GizmoMode mode) noexcept {
    switch (mode) {
    case GizmoMode::Translate:
        return "translate";
    case GizmoMode::Rotate:
        return "rotate";
    case GizmoMode::Scale:
        return "scale";
    default:
        return "translate";
    }
}

GizmoMode cycle_gizmo_mode(GizmoMode mode) noexcept {
    switch (mode) {
    case GizmoMode::Translate:
        return GizmoMode::Rotate;
    case GizmoMode::Rotate:
        return GizmoMode::Scale;
    case GizmoMode::Scale:
        return GizmoMode::Translate;
    default:
        return GizmoMode::Translate;
    }
}

const char* gizmo_mode_values_json() noexcept {
    static constexpr const char* kJson = R"(["translate","rotate","scale"])";
    return kJson;
}

TransformSpace normalize_transform_space(std::string_view value) noexcept {
    const std::string key = normalized_key(value);
    if (key == "local") {
        return TransformSpace::Local;
    }
    return TransformSpace::World;
}

const char* transform_space_to_string(TransformSpace space) noexcept {
    switch (space) {
    case TransformSpace::World:
        return "world";
    case TransformSpace::Local:
        return "local";
    default:
        return "world";
    }
}

const char* transform_space_values_json() noexcept {
    static constexpr const char* kJson = R"(["world","local"])";
    return kJson;
}

const char* gizmo_mode_contracts_schema_json() noexcept {
    static constexpr const char* kJson =
        R"({"schema":"gizmo_mode_native.v1",)"
        R"("source":"src/core/gizmo/gizmo_mode.py",)"
        R"("native_scope":["GizmoMode values","TransformGizmoMode alias values","TransformSpace values","default transform mode","default transform space","gizmo mode cycle order","gizmo origin resolution"],)"
        R"("python_fallback":["TransformGizmo object state","TransformController drag math","runtime object mutation","viewport event routing","gizmo draw data and picking"],)"
        R"("reason_python_fallback":"runtime gizmo state, drag controllers, picking, draw data, and object mutation remain Python-owned until those subsystems are ported"})";
    return kJson;
}

bool resolve_gizmo_origin(
    const double* position,
    const double* pivot_world,
    const double* gizmo_world,
    bool has_pivot_world,
    bool has_gizmo_world,
    bool is_helper_object,
    bool affect_pivot_only,
    double* out_origin
) noexcept {
    if (out_origin == nullptr) {
        return false;
    }

    double position_value[3] = {0.0, 0.0, 0.0};
    double pivot_value[3] = {0.0, 0.0, 0.0};
    double gizmo_value[3] = {0.0, 0.0, 0.0};
    const bool position_ok = read_vec3(position, position_value);
    const bool pivot_ok = has_pivot_world && read_vec3(pivot_world, pivot_value);
    const bool gizmo_ok = has_gizmo_world && read_vec3(gizmo_world, gizmo_value);

    if (is_helper_object && !affect_pivot_only) {
        if (gizmo_ok) {
            write_vec3(gizmo_value, out_origin);
            return true;
        }
        write_vec3(position_value, out_origin);
        return position_ok;
    }

    if (pivot_ok) {
        write_vec3(pivot_value, out_origin);
        return true;
    }
    if (gizmo_ok) {
        write_vec3(gizmo_value, out_origin);
        return true;
    }
    write_vec3(position_value, out_origin);
    return position_ok;
}

} // namespace ghostrigger::domain::core::gizmo::core::gizmo::gizmo_mode
