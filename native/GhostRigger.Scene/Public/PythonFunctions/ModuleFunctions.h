#pragma once

#include <cstddef>

namespace ghostrigger::scene {

#ifndef GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& fconstructe_basis_line_46_4c390260_native();
const NativeFunctionImplementation& normalize_line_56_203ee454_native();
const NativeFunctionImplementation& quat_to_basis_line_67_e86d6c6b_native();
const NativeFunctionImplementation& camera_basis_line_83_eed8416e_native();
const NativeFunctionImplementation& utc_now_iso_line_17_b20f8872_native();
const NativeFunctionImplementation& import_module_format_line_103_fb85bfec_native();
const NativeFunctionImplementation& normalise_resref_line_110_52ae0b09_native();
const NativeFunctionImplementation& module_from_input_line_114_a7371975_native();
const NativeFunctionImplementation& lyt_from_input_line_118_b47cc422_native();
const NativeFunctionImplementation& vis_from_input_line_125_b308cc05_native();
const NativeFunctionImplementation& room_wok_index_line_132_960b1b62_native();
const NativeFunctionImplementation& translation_matrix_line_140_0e8336ea_native();
const NativeFunctionImplementation& position_from_room_line_150_7b816fe4_native();
const NativeFunctionImplementation& position_from_hook_line_158_c0a228fb_native();
const NativeFunctionImplementation& room_distance_line_166_0081867a_native();
const NativeFunctionImplementation& nearest_room_line_173_2a37cff1_native();
const NativeFunctionImplementation& visibility_dict_line_179_ab5822c8_native();
const NativeFunctionImplementation& bounds_line_189_8abb30d8_native();
const NativeFunctionImplementation& build_lyt_room_graph_line_198_f7165eba_native();
const NativeFunctionImplementation& create_lyt_layout_line_340_97f1176d_native();
const NativeFunctionImplementation& add_room_to_lyt_line_355_96f89336_native();
const NativeFunctionImplementation& move_room_in_lyt_line_372_c47dfc7c_native();
const NativeFunctionImplementation& resolve_module_room_placement_line_43_53a9fd5b_native();
const NativeFunctionImplementation& resource_bytes_line_96_b2ad732d_native();
const NativeFunctionImplementation& dot3_line_42_627e4793_native();
const NativeFunctionImplementation& sub3_line_46_ac7929d6_native();
const NativeFunctionImplementation& add3_line_50_4fb43154_native();
const NativeFunctionImplementation& scale3_line_54_9f79e6e4_native();
const NativeFunctionImplementation& norm3_line_58_feb0e0e5_native();
const NativeFunctionImplementation& cross3_line_65_74e72371_native();
const NativeFunctionImplementation& get_character_registry_line_987_4ffb0beb_native();
const NativeFunctionImplementation& reset_character_registry_line_1000_086c29d4_native();
const NativeFunctionImplementation& vec3_line_10_91771333_native();
const NativeFunctionImplementation& import_module_format_line_70_342f215b_native();
const NativeFunctionImplementation& import_lyt_room_graph_line_77_38726069_native();
const NativeFunctionImplementation& normalise_resref_line_84_dc8a039a_native();
const NativeFunctionImplementation& module_from_input_line_88_750e55c5_native();
const NativeFunctionImplementation& graph_from_input_line_92_1dba7cb7_native();
const NativeFunctionImplementation& vis_from_input_line_98_d0959548_native();
const NativeFunctionImplementation& ensure_vis_line_105_0f1cc986_native();
const NativeFunctionImplementation& room_ids_line_117_d85dfe1c_native();
const NativeFunctionImplementation& visibility_dict_line_121_236bec87_native();
const NativeFunctionImplementation& set_visibility_line_139_387137db_native();
const NativeFunctionImplementation& persist_state_visibility_line_143_48e1c539_native();
const NativeFunctionImplementation& connections_line_147_976fb1dc_native();
const NativeFunctionImplementation& build_vis_editor_state_line_161_5d5f689f_native();
const NativeFunctionImplementation& preview_visibility_line_212_cfd3a926_native();
const NativeFunctionImplementation& add_visibility_link_line_229_9d1091a2_native();
const NativeFunctionImplementation& remove_visibility_link_line_257_19987c9f_native();
const NativeFunctionImplementation& make_full_visibility_line_281_9e4b6966_native();
const NativeFunctionImplementation& create_vis_data_line_297_95615bb2_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::scene
