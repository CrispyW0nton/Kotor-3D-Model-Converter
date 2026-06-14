#pragma once

namespace ghostrigger::domain::core::templates::core::templates::contracts {

const char* normalize_game_version(const char* game_version) noexcept;
int humanoid_bone_count(const char* game_version) noexcept;
int humanoid_animation_slot_count(const char* game_version) noexcept;
const char* humanoid_rig_source(const char* game_version) noexcept;
const char* detect_twoda_format(const unsigned char* data, unsigned int size) noexcept;
const char* twoda_cell_or_default(const char* value, const char* fallback) noexcept;
const char* split_twoda_line_json(const char* line) noexcept;
const char* templates_contracts_schema_json() noexcept;

} // namespace ghostrigger::domain::core::templates::core::templates::contracts
