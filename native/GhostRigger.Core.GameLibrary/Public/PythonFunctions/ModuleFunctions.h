#pragma once

#include <cstddef>

namespace ghostrigger::core::gamelibrary {

#ifndef GHOSTRIGGER_GAMELIBRARY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GAMELIBRARY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GAMELIBRARY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

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

} // namespace ghostrigger::core::gamelibrary
