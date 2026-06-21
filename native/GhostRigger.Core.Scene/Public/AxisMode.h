#pragma once

#include <array>
#include <string_view>

namespace ghostrigger::core::scene::core::scene::axis_mode {

using Matrix3 = std::array<double, 9>;
using Vec3 = std::array<double, 3>;
using Quat = std::array<double, 4>;

enum class AxisMode {
    View,
    Screen,
    World,
    Parent,
    Local,
    Gimbal,
    Grid,
    Working,
    Pick,
};

AxisMode normalize_axis_mode(std::string_view value) noexcept;
const char* axis_mode_to_string(AxisMode mode) noexcept;
const char* axis_mode_label(AxisMode mode) noexcept;
const char* axis_mode_values_json() noexcept;
Matrix3 identity_basis() noexcept;
Matrix3 finite_basis(const double* basis9) noexcept;
Vec3 normalize_vector(Vec3 value, Vec3 fallback) noexcept;
Matrix3 quat_to_basis(const double* quat4) noexcept;
const char* axis_mode_contracts_schema_json() noexcept;

} // namespace ghostrigger::core::scene::core::scene::axis_mode
