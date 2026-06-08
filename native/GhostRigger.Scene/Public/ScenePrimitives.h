#pragma once

#include <array>
#include <string_view>

namespace ghostrigger::scene::core::scene::scene_primitives {

using Vec3 = std::array<double, 3>;

struct TransformDefaults {
    Vec3 position;
    Vec3 rotation;
    Vec3 scale;
};

struct PivotDefaults {
    Vec3 position_local;
    Vec3 rotation_local;
    bool enabled;
};

Vec3 sanitize_vec3(const double* values3, Vec3 fallback) noexcept;
TransformDefaults default_transform() noexcept;
PivotDefaults default_pivot() noexcept;
bool pivot_values_are_valid(const double* position3, const double* rotation3) noexcept;
const char* sanitize_game_code(std::string_view value) noexcept;
const char* scene_resource_ref_defaults_json() noexcept;
bool metadata_key_is_persisted(std::string_view key) noexcept;
const char* scene_primitives_schema_json() noexcept;

} // namespace ghostrigger::scene::core::scene::scene_primitives
