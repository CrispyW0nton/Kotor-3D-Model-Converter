#pragma once

#include <string_view>

namespace ghostrigger::gizmo::core::gizmo::gizmo_mode {

enum class GizmoMode {
    Translate,
    Rotate,
    Scale,
};

enum class TransformSpace {
    World,
    Local,
};

GizmoMode normalize_gizmo_mode(std::string_view value) noexcept;
const char* gizmo_mode_to_string(GizmoMode mode) noexcept;
GizmoMode cycle_gizmo_mode(GizmoMode mode) noexcept;
const char* gizmo_mode_values_json() noexcept;
TransformSpace normalize_transform_space(std::string_view value) noexcept;
const char* transform_space_to_string(TransformSpace space) noexcept;
const char* transform_space_values_json() noexcept;
const char* gizmo_mode_contracts_schema_json() noexcept;

} // namespace ghostrigger::gizmo::core::gizmo::gizmo_mode
