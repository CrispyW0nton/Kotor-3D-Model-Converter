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

const NativeFunctionImplementation& resourceentry_read_line_186_03bea365_native();
const NativeFunctionImplementation& keybifreader_construct_line_205_cf570382_native();
const NativeFunctionImplementation& keybifreader_load_line_214_75fa6781_native();
const NativeFunctionImplementation& keybifreader_get_line_391_63f58f54_native();
const NativeFunctionImplementation& keybifreader_list_type_line_419_6f3477e8_native();
const NativeFunctionImplementation& keybifreader_list_all_types_line_441_fbf76cca_native();
const NativeFunctionImplementation& keybifreader_list_all_resources_line_445_55202d73_native();
const NativeFunctionImplementation& erfreader_construct_line_458_20e07f2c_native();
const NativeFunctionImplementation& erfreader_load_line_463_787a1e59_native();
const NativeFunctionImplementation& erfreader_load_v1_from_tables_line_501_00997c81_native();
const NativeFunctionImplementation& erfreader_load_v1_line_525_48cb5f73_native();
const NativeFunctionImplementation& erfreader_get_line_535_3e2e3feb_native();
const NativeFunctionImplementation& erfreader_list_type_line_538_73602c7a_native();
const NativeFunctionImplementation& erfreader_list_all_line_541_8c5287c8_native();
const NativeFunctionImplementation& gamelibrary_construct_line_674_79ae6ceb_native();
const NativeFunctionImplementation& gamelibrary_set_k1_dir_line_690_bc728836_native();
const NativeFunctionImplementation& gamelibrary_set_k2_dir_line_697_f18ba4c4_native();
const NativeFunctionImplementation& gamelibrary_scan_line_704_943f553e_native();
const NativeFunctionImplementation& gamelibrary_scan_game_line_861_11feb0eb_native();
const NativeFunctionImplementation& gamelibrary_read_mdl_metadata_line_1021_49fe64f9_native();
const NativeFunctionImplementation& gamelibrary_get_2da_line_1036_e392fe83_native();
const NativeFunctionImplementation& gamelibrary_get_2da_raw_line_1060_d6cd5828_native();
const NativeFunctionImplementation& gamelibrary_list_2da_names_line_1083_66e75be4_native();
const NativeFunctionImplementation& gamelibrary_list_resources_line_1093_d309a480_native();
const NativeFunctionImplementation& gamelibrary_get_resource_data_line_1100_da175a53_native();
const NativeFunctionImplementation& gamelibrary_search_line_1125_3a92a130_native();
const NativeFunctionImplementation& gamelibrary_list_models_by_class_line_1131_305675e6_native();
const NativeFunctionImplementation& gamelibrary_list_textures_line_1147_14298a13_native();
const NativeFunctionImplementation& gamelibrary_get_tlk_string_line_1153_e6a818a7_native();
const NativeFunctionImplementation& gamelibrary_get_texture_data_line_1180_0a58651f_native();
const NativeFunctionImplementation& gamelibrary_get_model_data_line_1331_84a35054_native();
const NativeFunctionImplementation& gamelibrary_extract_to_folder_line_1375_1f447f19_native();
const NativeFunctionImplementation& gamelibrary_scan_texture_names_line_1407_2c8a495d_native();
const NativeFunctionImplementation& gamelibrary_detect_texture_ext_line_1441_cab77586_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gamelibrary
