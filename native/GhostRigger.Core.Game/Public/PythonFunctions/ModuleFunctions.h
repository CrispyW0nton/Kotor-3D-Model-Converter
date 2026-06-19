#pragma once

#include <cstddef>

namespace ghostrigger::core::game {

#ifndef GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& res_type_name_line_147_01728658_native();
const NativeFunctionImplementation& res_type_ext_line_152_be86c927_native();
const NativeFunctionImplementation& read_2da_from_library_line_409_66611753_native();
const NativeFunctionImplementation& read_gff_from_library_line_426_a81c1965_native();
const NativeFunctionImplementation& list_all_resources_line_443_a95d6a3e_native();
const NativeFunctionImplementation& model_root_name_line_14_b3f36a68_native();
const NativeFunctionImplementation& apply_known_skin_bone_map_normalisations_line_26_e7cbd46f_native();
const NativeFunctionImplementation& normalise_bastila_headless_body_torso_line_36_71f88dd3_native();
const NativeFunctionImplementation& res_key_line_81_d89d1922_native();
const NativeFunctionImplementation& load_model_from_bytes_line_101_39077bf8_native();
const NativeFunctionImplementation& load_model_from_file_line_159_bcd175fa_native();
const NativeFunctionImplementation& game_name_line_213_ffd92671_native();
const NativeFunctionImplementation& is_null_supermodel_line_228_ebcc9ea4_native();
const NativeFunctionImplementation& configure_supermodel_resource_manager_line_232_e7c74104_native();
const NativeFunctionImplementation& load_supermodel_chain_line_240_1efde3d8_native();
const NativeFunctionImplementation& get_valid_animation_slots_line_290_da9e4e42_native();
const NativeFunctionImplementation& resolve_animation_slot_line_310_a4fd9bc2_native();
const NativeFunctionImplementation& patch_tpc_header_line_362_39366810_native();
const NativeFunctionImplementation& load_tpc_as_pil_line_407_d07caf95_native();
const NativeFunctionImplementation& mdl_to_kotormodel_line_511_6e446fd7_native();
const NativeFunctionImplementation& detect_version_from_bytes_line_576_3d33ba69_native();
const NativeFunctionImplementation& is_xbox_from_bytes_line_602_879408d0_native();
const NativeFunctionImplementation& detect_version_line_613_21d121b9_native();
const NativeFunctionImplementation& convert_node_line_626_ac727525_native();
const NativeFunctionImplementation& read_mesh_line_698_f14c7b47_native();
const NativeFunctionImplementation& read_skin_textures_line_956_3888f767_native();
const NativeFunctionImplementation& read_skin_weights_line_985_8c4cf503_native();
const NativeFunctionImplementation& read_dangly_line_1173_9f6cab8d_native();
const NativeFunctionImplementation& read_light_line_1225_3bbbde20_native();
const NativeFunctionImplementation& read_controllers_line_1258_36619c08_native();
const NativeFunctionImplementation& convert_anim_line_1306_c5549544_native();
const NativeFunctionImplementation& walk_nodes_line_1335_df6bf8b4_native();
const NativeFunctionImplementation& fill_missing_normals_line_1355_7ef28257_native();
const NativeFunctionImplementation& apply_bind_pose_line_1401_71383db6_native();
const NativeFunctionImplementation& iter_nodes_dfs_line_1487_12824831_native();
const NativeFunctionImplementation& find_node_exact_line_1504_bc652d17_native();
const NativeFunctionImplementation& reparent_head_nodes_line_1521_d4207389_native();
const NativeFunctionImplementation& is_pykotor_available_line_29_90071d4f_native();
const NativeFunctionImplementation& fill_mesh_data_line_34_2da510e0_native();
const NativeFunctionImplementation& list_animations_via_pykotor_line_40_982d6f81_native();
const NativeFunctionImplementation& compare_model_animations_line_56_eade3dac_native();
const NativeFunctionImplementation& validate_animations_via_pykotor_line_92_78ef2a24_native();
const NativeFunctionImplementation& ensure_pykotor_mdl_binary_fixes_line_120_91ced2ac_native();
const NativeFunctionImplementation& raise_or_bypass_line_172_ebe23a5b_native();
const NativeFunctionImplementation& check_pykotor_compat_line_188_e8e4995c_native();
const NativeFunctionImplementation& ghostrigger_trimesh_read_line_295_f8a97a2a_native();
const NativeFunctionImplementation& patch_load_node_mdx_zero_line_416_82445f13_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::game
