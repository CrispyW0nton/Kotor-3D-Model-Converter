#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gamelibrary {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_resources_game_library_keybifreader_load_resolve_path_ci_line_247_71476e69_descriptor_json();
const char* src_resources_game_library_keybifreader_load_get_bif_entry_line_293_e13dddf4_descriptor_json();
const char* src_resources_game_library_gamelibrary_scan_game_add_entry_line_866_8adb4fa7_descriptor_json();
const char* src_resources_game_library_gamelibrary_scan_game_tp_sort_key_line_934_09b9b401_descriptor_json();
const char* src_resources_game_library_gamelibrary_get_texture_data_search_override_for_line_1196_a309eabc_descriptor_json();
const char* src_resources_game_library_gamelibrary_get_texture_data_search_erfs_for_line_1216_ca75d9e0_descriptor_json();
const char* src_resources_game_library_gamelibrary_get_texture_data_search_erfs_for_erf_quality_line_1224_3d112bf2_descriptor_json();
const char* src_resources_game_library_gamelibrary_get_texture_data_search_key_for_line_1250_ba7fc3ee_descriptor_json();
const char* src_resources_game_library_gamelibrary_get_texture_data_search_game_line_1262_f8133549_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gamelibrary
