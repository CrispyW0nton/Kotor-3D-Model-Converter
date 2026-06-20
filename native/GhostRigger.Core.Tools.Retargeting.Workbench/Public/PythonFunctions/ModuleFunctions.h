#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::retargeting::workbench {

#ifndef GHOSTRIGGER_WINDOWS_ANIMATIONRETARGETWORKBENCH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WINDOWS_ANIMATIONRETARGETWORKBENCH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WINDOWS_ANIMATIONRETARGETWORKBENCH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& populate_retarget_mode_combo_line_793_e0c7b032_native();
const NativeFunctionImplementation& combo_current_retarget_mode_line_812_445ddc05_native();
const NativeFunctionImplementation& pending_status_for_mode_line_821_43e64cec_native();
const NativeFunctionImplementation& mode_status_for_mode_line_829_7a8a9003_native();
const NativeFunctionImplementation& human_kind_line_839_cc62b965_native();
const NativeFunctionImplementation& verified_source_to_aurora_solver_options_line_851_549a3da5_native();
const NativeFunctionImplementation& basis_conversion_from_metadata_line_874_417e4279_native();
const NativeFunctionImplementation& build_source_clip_preview_model_line_32_7c14f1c2_native();
const NativeFunctionImplementation& apply_compact_preview_positions_line_99_3bf4df82_native();
const NativeFunctionImplementation& source_clip_parent_local_position_line_115_38a0f9ee_native();
const NativeFunctionImplementation& rotate_world_delta_to_parent_local_line_145_57c8bf0a_native();
const NativeFunctionImplementation& source_clip_animation_rows_line_159_71a15d98_native();
const NativeFunctionImplementation& animation_length_line_205_791e7d64_native();
const NativeFunctionImplementation& optional_float_line_218_afaaa5a4_native();
const NativeFunctionImplementation& optional_int_line_228_d1b4f475_native();
const NativeFunctionImplementation& append_mesh_preview_nodes_line_235_73b55fcd_native();
const NativeFunctionImplementation& apply_transform_to_node_line_281_00ea90d0_native();
const NativeFunctionImplementation& bounds_from_clip_line_289_539e075b_native();
const NativeFunctionImplementation& merge_bounds_line_313_5038bb1e_native();
const NativeFunctionImplementation& fconstructe_position_line_329_ab6d559f_native();
const NativeFunctionImplementation& fconstructe_quat_line_343_fa611792_native();
const NativeFunctionImplementation& radius_for_bounds_line_361_fdab8f35_native();
const NativeFunctionImplementation& root_name_for_clip_line_368_b9e34795_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::retargeting::workbench
