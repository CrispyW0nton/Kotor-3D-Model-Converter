#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::contentbrowser {

#ifndef GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_CONTENTBROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& coerce_resource_query_line_167_7f44b7c9_native();
const NativeFunctionImplementation& restype_to_extension_line_435_31818d30_native();
const NativeFunctionImplementation& records_from_install_line_442_d584abb3_native();
const NativeFunctionImplementation& override_records_line_460_4ed75a34_native();
const NativeFunctionImplementation& erf_records_line_484_ffbf89da_native();
const NativeFunctionImplementation& bif_records_line_522_06835f17_native();
const NativeFunctionImplementation& record_line_553_c54864de_native();
const NativeFunctionImplementation& record_matches_line_585_b183a772_native();
const NativeFunctionImplementation& sort_records_line_602_7ec36ae3_native();
const NativeFunctionImplementation& dedupe_records_line_616_04bd525c_native();
const NativeFunctionImplementation& shadow_warnings_line_628_7bbc96a1_native();
const NativeFunctionImplementation& missing_message_line_639_f3c2430b_native();
const NativeFunctionImplementation& safe_path_size_line_645_b0a8d605_native();
const NativeFunctionImplementation& clean_text_line_654_2cfa996a_native();
const NativeFunctionImplementation& clean_restype_line_663_900cb5d5_native();
const NativeFunctionImplementation& clean_game_line_672_1069848e_native();
const NativeFunctionImplementation& manager_game_name_line_684_fe85bf0b_native();
const NativeFunctionImplementation& manager_install_line_688_1c893257_native();
const NativeFunctionImplementation& resource_manager_type_id_line_696_8c70051d_native();
const NativeFunctionImplementation& resource_manager_restype_line_706_d79aaf25_native();
const NativeFunctionImplementation& known_resource_type_ids_line_715_45edd331_native();
const NativeFunctionImplementation& detect_kotor_dirs_line_59_ee1e7930_native();
const NativeFunctionImplementation& save_config_line_140_8365201b_native();
const NativeFunctionImplementation& load_config_line_159_9af175df_native();
const NativeFunctionImplementation& list_all_candidates_line_172_d2f92ee3_native();
const NativeFunctionImplementation& is_kotor_dir_line_212_d86eeb54_native();
const NativeFunctionImplementation& steam_library_paths_line_260_498895fc_native();
const NativeFunctionImplementation& steam_candidates_line_324_a1990e7e_native();
const NativeFunctionImplementation& gog_candidates_line_369_c389a1af_native();
const NativeFunctionImplementation& default_candidates_line_422_ea4e7fe6_native();
const NativeFunctionImplementation& unique_paths_line_468_c630b2e5_native();
const NativeFunctionImplementation& windows_drive_roots_line_484_a5b9d18d_native();
const NativeFunctionImplementation& registry_path_values_line_500_35fa6f7c_native();
const NativeFunctionImplementation& windows_registry_steam_roots_line_520_8c7d3c78_native();
const NativeFunctionImplementation& windows_registry_kotor_candidates_line_539_219c97c3_native();
const NativeFunctionImplementation& windows_uninstall_kotor_candidates_line_568_92ada9dd_native();
const NativeFunctionImplementation& res_ext_line_125_2276852b_native();
const NativeFunctionImplementation& res_name_line_130_15b8bcd2_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::contentbrowser
