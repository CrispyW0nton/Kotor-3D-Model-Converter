#pragma once

#include <cstddef>

namespace ghostrigger::core::animation {

#ifndef GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ANIMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& lerp_line_326_ccd49f0b_native();
const NativeFunctionImplementation& lerp3_line_330_d78b4641_native();
const NativeFunctionImplementation& slerp_line_338_888e1d94_native();
const NativeFunctionImplementation& is_fconstructe_vec_line_371_80e75373_native();
const NativeFunctionImplementation& ensure_quat_sign_consistency_line_376_245dd9e4_native();
const NativeFunctionImplementation& interp_channel_line_416_30ecba82_native();
const NativeFunctionImplementation& normalize_quat_xyzw_line_532_5ac44082_native();
const NativeFunctionImplementation& controller_matches_line_541_deb22beb_native();
const NativeFunctionImplementation& sample_controller_absolute_line_548_8c8f34d5_native();
const NativeFunctionImplementation& compose_transform_line_575_69723e71_native();
const NativeFunctionImplementation& evaluate_aurora_animation_pose_line_593_25410bcc_native();
const NativeFunctionImplementation& merge_usecomp_animations_line_1737_0f5aa4af_native();
const NativeFunctionImplementation& build_bone_remap_line_1756_49c68eb2_native();
const NativeFunctionImplementation& retarget_usecomp_line_1860_e8730c26_native();
const NativeFunctionImplementation& get_ctrl_line_1916_97e63288_native();
const NativeFunctionImplementation& batch_export_animations_line_1331_05a3fc02_native();
const NativeFunctionImplementation& mat4_identity_line_1415_1a0231a6_native();
const NativeFunctionImplementation& mat4_mul_line_1420_39fc4bfb_native();
const NativeFunctionImplementation& mat4_from_sqt_line_1432_7eefb660_native();
const NativeFunctionImplementation& mat4_inverse_trs_line_1481_6714de78_native();
const NativeFunctionImplementation& build_world_transforms_line_1514_82257b22_native();
const NativeFunctionImplementation& slerp_quat_line_1548_644ef13a_native();
const NativeFunctionImplementation& quat_to_euler_xyz_line_1583_d602106e_native();
const NativeFunctionImplementation& safe_filename_line_1606_7580dfda_native();
const NativeFunctionImplementation& classify_skinning_species_line_141_a7a903d5_native();
const NativeFunctionImplementation& explicit_skin_formula_override_line_196_6b278fbf_native();
const NativeFunctionImplementation& active_skin_formula_line_201_14d466e5_native();
const NativeFunctionImplementation& quat_to_mat4_line_245_1b945e78_native();
const NativeFunctionImplementation& mat4_mul_py_line_269_bf3579a4_native();
const NativeFunctionImplementation& mat4_identity_py_line_281_5178349d_native();
const NativeFunctionImplementation& mat4_translate_py_line_285_7994369d_native();
const NativeFunctionImplementation& mat4_to_flat_col_line_289_49386053_native();
const NativeFunctionImplementation& mat4_rotation_only_py_line_298_2fb6568c_native();
const NativeFunctionImplementation& mat4_invert_py_line_1323_37f6c614_native();
const NativeFunctionImplementation& validate_tbn_line_1751_77cb7c15_native();
const NativeFunctionImplementation& load_profiles_line_79_e95213b9_native();
const NativeFunctionImplementation& contains_any_line_110_6435d954_native();
const NativeFunctionImplementation& enum_value_line_114_25301b80_native();
const NativeFunctionImplementation& node_names_from_model_line_119_6f20dc36_native();
const NativeFunctionImplementation& has_skin_from_nodes_line_126_58133f04_native();
const NativeFunctionImplementation& taxonomy_from_model_line_140_dc777ddc_native();
const NativeFunctionImplementation& context_from_args_line_150_7419fa6f_native();
const NativeFunctionImplementation& specific_profile_for_context_line_191_c9346b62_native();
const NativeFunctionImplementation& species_for_context_line_269_9e9e7859_native();
const NativeFunctionImplementation& profile_matches_line_294_1074b75f_native();
const NativeFunctionImplementation& resolve_skinning_profile_line_327_fb033e86_native();
const NativeFunctionImplementation& classify_skinning_species_line_393_21cf51aa_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::animation
