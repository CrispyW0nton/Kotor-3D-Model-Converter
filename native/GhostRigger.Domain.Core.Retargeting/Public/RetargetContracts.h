#pragma once

#include <string>
#include <string_view>

namespace ghostrigger::domain::core::retargeting::core::retargeting::retarget_contracts {

enum class RetargetMode {
    KotorToKotor,
    KotorToUnreal,
    UnrealToKotor,
    Invalid,
};

enum class KotorOutputAnimationNameMode {
    VanillaSlot,
    CustomPatch,
    Invalid,
};

RetargetMode coerce_retarget_mode(std::string_view value) noexcept;
KotorOutputAnimationNameMode coerce_kotor_output_name_mode(std::string_view value) noexcept;
bool is_kotor_output_mode(RetargetMode mode) noexcept;
bool is_kotor_output_mode(std::string_view mode) noexcept;
const char* retarget_mode_to_string(RetargetMode mode) noexcept;
const char* kotor_output_name_mode_to_string(KotorOutputAnimationNameMode mode) noexcept;
const char* retarget_mode_specs_json() noexcept;
std::string validate_custom_kotor_animation_name(std::string_view name);
std::string sanitize_unreal_clip_name(std::string_view name);
std::string validate_unreal_clip_name(std::string_view name);
const char* retarget_contracts_schema_json() noexcept;

} // namespace ghostrigger::domain::core::retargeting::core::retargeting::retarget_contracts
