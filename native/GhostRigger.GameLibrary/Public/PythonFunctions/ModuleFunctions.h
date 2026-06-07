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

const char* src_resources_game_detector_detect_kotor_dirs_line_59_58c316ed_descriptor_json();
const char* src_resources_game_detector_save_config_line_140_715b3b16_descriptor_json();
const char* src_resources_game_detector_load_config_line_159_231807ce_descriptor_json();
const char* src_resources_game_detector_list_all_candidates_line_172_cfdbd573_descriptor_json();
const char* src_resources_game_detector_is_kotor_dir_line_212_41b67c1f_descriptor_json();
const char* src_resources_game_detector_steam_library_paths_line_260_6ffd514b_descriptor_json();
const char* src_resources_game_detector_steam_candidates_line_324_c5aaa94d_descriptor_json();
const char* src_resources_game_detector_gog_candidates_line_369_7c4b8b65_descriptor_json();
const char* src_resources_game_detector_default_candidates_line_422_4e4dc2c4_descriptor_json();
const char* src_resources_game_detector_unique_paths_line_468_37e6a31e_descriptor_json();
const char* src_resources_game_detector_windows_drive_roots_line_484_9fabc71e_descriptor_json();
const char* src_resources_game_detector_registry_path_values_line_500_c1d5de92_descriptor_json();
const char* src_resources_game_detector_windows_registry_steam_roots_line_520_b845a039_descriptor_json();
const char* src_resources_game_detector_windows_registry_kotor_candidates_line_539_84aa7014_descriptor_json();
const char* src_resources_game_detector_windows_uninstall_kotor_candidates_line_568_2f969042_descriptor_json();
const char* src_resources_game_library_res_ext_line_125_0163fdc4_descriptor_json();
const char* src_resources_game_library_res_name_line_130_c437aa6c_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gamelibrary
