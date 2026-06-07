#pragma once

#include <cstddef>

namespace ghostrigger::tools::sequenceeditor {

#ifndef GHOSTRIGGER_TOOLS_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_TOOLS_SEQUENCEEDITOR_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& animation_display_name_line_114_1b1dca2a_native();
const NativeFunctionImplementation& animation_row_label_line_127_2e7e3436_native();
const NativeFunctionImplementation& animation_base_display_name_line_138_03aa7c07_native();
const NativeFunctionImplementation& animation_set_context_line_167_1f7046f6_native();
const NativeFunctionImplementation& animation_action_label_line_175_bd63af3f_native();
const NativeFunctionImplementation& humanize_animation_slot_line_182_a124c22c_native();
const NativeFunctionImplementation& animation_game_label_line_191_9ffeda17_native();
const NativeFunctionImplementation& game_from_model_line_202_88085dc4_native();
const NativeFunctionImplementation& inspect_sequence_asset_line_24_9dc7218d_native();
const NativeFunctionImplementation& vec3_line_24_4114c5a2_native();
const NativeFunctionImplementation& quat_line_32_50d74e5d_native();
const NativeFunctionImplementation& ease_line_11_a760953f_native();
const NativeFunctionImplementation& lerp_number_line_22_fb55d093_native();
const NativeFunctionImplementation& interpolate_values_line_26_d369775d_native();
const NativeFunctionImplementation& evaluate_keyframes_line_59_1110b1b0_native();
const NativeFunctionImplementation& ensure_sequence_object_id_line_16_57d9eb8d_native();
const NativeFunctionImplementation& infer_target_type_line_36_fa8d664b_native();
const NativeFunctionImplementation& utc_now_iso_line_17_86773d91_native();
const NativeFunctionImplementation& validate_frame_rate_line_57_0072f6d4_native();
const NativeFunctionImplementation& sequence_to_json_line_19_1aef18d8_native();
const NativeFunctionImplementation& sequence_from_json_line_23_c40978d0_native();
const NativeFunctionImplementation& save_sequence_file_line_31_db800667_native();
const NativeFunctionImplementation& load_sequence_file_line_45_6dee483d_native();
const NativeFunctionImplementation& register_track_line_16_585a4ce8_native();
const NativeFunctionImplementation& transform_value_line_12_607baaf2_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::sequenceeditor
