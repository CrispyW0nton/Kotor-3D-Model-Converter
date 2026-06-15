#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::resourcebrowser {

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

const NativeFunctionImplementation& keybifreader_load_resolve_path_ci_line_247_71476e69_native();
const NativeFunctionImplementation& keybifreader_load_get_bif_entry_line_293_e13dddf4_native();
const NativeFunctionImplementation& gamelibrary_scan_game_add_entry_line_866_8adb4fa7_native();
const NativeFunctionImplementation& gamelibrary_scan_game_tp_sort_key_line_934_09b9b401_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_override_for_line_1196_a309eabc_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_erfs_for_line_1216_ca75d9e0_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_erfs_for_erf_quality_line_1224_3d112bf2_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_key_for_line_1250_ba7fc3ee_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_game_line_1262_f8133549_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::resourcebrowser
