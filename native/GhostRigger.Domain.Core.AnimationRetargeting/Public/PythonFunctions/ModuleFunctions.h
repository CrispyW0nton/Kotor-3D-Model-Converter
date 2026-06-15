#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::animationretargeting {

#ifndef GHOSTRIGGER_ANIMATIONRETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ANIMATIONRETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ANIMATIONRETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& nodes_by_name_line_65_e3de5782_native();
const NativeFunctionImplementation& candidate_names_line_76_b6eddd65_native();
const NativeFunctionImplementation& clean_manual_mapping_line_88_8f23256c_native();
const NativeFunctionImplementation& build_bone_map_line_100_8e82d5c4_native();
const NativeFunctionImplementation& sub3_line_149_03d6213f_native();
const NativeFunctionImplementation& add3_line_157_c4cbd1f2_native();
const NativeFunctionImplementation& mul3_line_165_14d84c21_native();
const NativeFunctionImplementation& normal_quat_line_169_98a854c7_native();
const NativeFunctionImplementation& quat_conjugate_line_177_0afd563e_native();
const NativeFunctionImplementation& quat_mul_line_182_481c2862_native();
const NativeFunctionImplementation& retarget_rotation_line_193_550164d3_native();
const NativeFunctionImplementation& world_positions_by_key_line_198_09fd658e_native();
const NativeFunctionImplementation& height_from_positions_line_221_e0f49b0c_native();
const NativeFunctionImplementation& position_delta_scale_line_226_35d691fe_native();
const NativeFunctionImplementation& retarget_pose_line_244_c1c102c3_native();
const NativeFunctionImplementation& scaled_position_values_line_296_75cae199_native();
const NativeFunctionImplementation& retarget_animation_line_308_238ad410_native();
const NativeFunctionImplementation& import_character_builder_line_190_09eda0fb_native();
const NativeFunctionImplementation& norm_game_line_198_84abe7d0_native();
const NativeFunctionImplementation& norm_part_line_209_623f1163_native();
const NativeFunctionImplementation& read_json_line_222_670073be_native();
const NativeFunctionImplementation& manifest_path_for_template_line_231_dbebd530_native();
const NativeFunctionImplementation& infer_part_line_236_93e262d0_native();
const NativeFunctionImplementation& npc_numbered_variant_base_resref_line_253_faf35258_native();
const NativeFunctionImplementation& resolve_model_variant_source_resref_line_279_d9b2c09f_native();
const NativeFunctionImplementation& matches_query_line_307_2c5a3371_native();
const NativeFunctionImplementation& dedupe_options_line_326_cbb29e1f_native();
const NativeFunctionImplementation& list_bundled_templates_line_338_067a378e_native();
const NativeFunctionImplementation& list_canonical_skeleton_sources_line_398_34b733d8_native();
const NativeFunctionImplementation& build_game_template_options_line_442_cf0ea35f_native();
const NativeFunctionImplementation& list_skeleton_templates_line_512_254d6d6a_native();
const NativeFunctionImplementation& option_summary_line_591_42834424_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::animationretargeting
