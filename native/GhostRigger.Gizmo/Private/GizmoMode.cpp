#include "GizmoMode.h"

#include <cctype>
#include <string>

namespace ghostrigger::gizmo::core::gizmo::gizmo_mode {
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
        R"("native_scope":["GizmoMode values","TransformGizmoMode alias values","TransformSpace values","default transform mode","default transform space","gizmo mode cycle order"],)"
        R"("python_fallback":["TransformGizmo object state","TransformController drag math","runtime object mutation","viewport event routing","gizmo draw data and picking"],)"
        R"("reason_python_fallback":"runtime gizmo state, drag controllers, picking, draw data, and object mutation remain Python-owned until those subsystems are ported"})";
    return kJson;
}

} // namespace ghostrigger::gizmo::core::gizmo::gizmo_mode
