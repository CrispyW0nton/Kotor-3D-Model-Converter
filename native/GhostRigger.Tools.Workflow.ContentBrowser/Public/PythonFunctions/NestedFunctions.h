#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::contentbrowser {

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

const NativeFunctionImplementation& resourceloadingmixin_load_resource_model_on_ui_thread_progress_line_363_2134aec6_native();
const NativeFunctionImplementation& resourceloadingmixin_select_module_mesh_by_name_from_ipc_node_source_line_1121_4a1424e9_native();
const NativeFunctionImplementation& resourceloadingmixin_select_module_mesh_by_name_from_ipc_matches_line_1142_18e12a82_native();
const NativeFunctionImplementation& keybifreader_load_resolve_path_ci_line_247_b56cdd64_native();
const NativeFunctionImplementation& keybifreader_load_get_bif_entry_line_293_436944cc_native();
const NativeFunctionImplementation& gamelibrary_scan_game_add_entry_line_866_ae350af4_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_override_for_line_1196_c132d909_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_erfs_for_line_1216_0bb2a9d9_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_key_for_line_1250_1f3175cc_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_game_line_1262_47cb2c18_native();
const NativeFunctionImplementation& gamelibrary_scan_game_tp_sort_key_line_934_b0ee4577_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_search_erfs_for_erf_quality_line_1224_2035135c_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::contentbrowser
