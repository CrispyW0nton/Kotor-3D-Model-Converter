#pragma once

#include <cstddef>

namespace ghostrigger::tools::resourcebrowser {

#ifndef GHOSTRIGGER_TOOLS_RESOURCEBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_RESOURCEBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_RESOURCEBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& key_line_98_0520e2cf_native();
const NativeFunctionImplementation& texture_name_candidates_line_110_f1e75d5f_native();
const NativeFunctionImplementation& decode_texture_line_748_23e8416a_native();
const NativeFunctionImplementation& tpc_uncompressed_txi_line_877_211ae331_native();
const NativeFunctionImplementation& tpc_info_line_912_ce2f9944_native();
const NativeFunctionImplementation& is_tpc_line_943_3763289e_native();
const NativeFunctionImplementation& get_manager_line_1014_7b60640d_native();
const NativeFunctionImplementation& reset_manager_line_1024_a1b1addf_native();
const NativeFunctionImplementation& resolve_model_textures_line_1034_771e23a2_native();
const NativeFunctionImplementation& audit_model_textures_line_1149_37515999_native();
const NativeFunctionImplementation& identify_texture_source_line_1240_5185a261_native();
const NativeFunctionImplementation& parse_txi_for_alpha_line_1278_ef05cf3e_native();
const NativeFunctionImplementation& apply_alpha_fix_line_1313_55e1139e_native();
const NativeFunctionImplementation& coerce_resource_query_line_167_aa2b5698_native();
const NativeFunctionImplementation& restype_to_extension_line_435_d168dbf6_native();
const NativeFunctionImplementation& records_from_install_line_442_29a1399c_native();
const NativeFunctionImplementation& override_records_line_460_fa1405f7_native();
const NativeFunctionImplementation& erf_records_line_484_f262248d_native();
const NativeFunctionImplementation& bif_records_line_522_923b63b9_native();
const NativeFunctionImplementation& record_line_553_2745da10_native();
const NativeFunctionImplementation& record_matches_line_585_f4a92796_native();
const NativeFunctionImplementation& sort_records_line_602_cf3d7f84_native();
const NativeFunctionImplementation& dedupe_records_line_616_788f2d14_native();
const NativeFunctionImplementation& shadow_warnings_line_628_0fd0c506_native();
const NativeFunctionImplementation& missing_message_line_639_8fea0f4d_native();
const NativeFunctionImplementation& safe_path_size_line_645_ca4cce06_native();
const NativeFunctionImplementation& clean_text_line_654_ba113744_native();
const NativeFunctionImplementation& clean_restype_line_663_96e19284_native();
const NativeFunctionImplementation& clean_game_line_672_dc0cf339_native();
const NativeFunctionImplementation& manager_game_name_line_684_d824b250_native();
const NativeFunctionImplementation& manager_install_line_688_f11c7825_native();
const NativeFunctionImplementation& resource_manager_type_id_line_696_88dd7962_native();
const NativeFunctionImplementation& resource_manager_restype_line_706_feb4e7a7_native();
const NativeFunctionImplementation& known_resource_type_ids_line_715_dd065008_native();
const NativeFunctionImplementation& role_text_line_273_f07acd64_native();
const NativeFunctionImplementation& as_iter_line_282_aeff2e47_native();
const NativeFunctionImplementation& detect_kotor_dirs_line_59_58c316ed_native();
const NativeFunctionImplementation& save_config_line_140_715b3b16_native();
const NativeFunctionImplementation& load_config_line_159_231807ce_native();
const NativeFunctionImplementation& list_all_candidates_line_172_cfdbd573_native();
const NativeFunctionImplementation& is_kotor_dir_line_212_41b67c1f_native();
const NativeFunctionImplementation& steam_library_paths_line_260_6ffd514b_native();
const NativeFunctionImplementation& steam_candidates_line_324_c5aaa94d_native();
const NativeFunctionImplementation& gog_candidates_line_369_7c4b8b65_native();
const NativeFunctionImplementation& default_candidates_line_422_4e4dc2c4_native();
const NativeFunctionImplementation& unique_paths_line_468_37e6a31e_native();
const NativeFunctionImplementation& windows_drive_roots_line_484_9fabc71e_native();
const NativeFunctionImplementation& registry_path_values_line_500_c1d5de92_native();
const NativeFunctionImplementation& windows_registry_steam_roots_line_520_b845a039_native();
const NativeFunctionImplementation& windows_registry_kotor_candidates_line_539_84aa7014_native();
const NativeFunctionImplementation& windows_uninstall_kotor_candidates_line_568_2f969042_native();
const NativeFunctionImplementation& res_ext_line_125_0163fdc4_native();
const NativeFunctionImplementation& res_name_line_130_c437aa6c_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::resourcebrowser
