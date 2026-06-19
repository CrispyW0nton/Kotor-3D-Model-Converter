#pragma once

#include <cstddef>

namespace ghostrigger::core::level {

#ifndef GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_LEVEL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& leveltransform_to_dict_line_57_822773a7_native();
const NativeFunctionImplementation& walkmeshreference_to_dict_line_90_16009c05_native();
const NativeFunctionImplementation& roominstance_to_dict_line_138_e1b48db5_native();
const NativeFunctionImplementation& moduleinstance_to_dict_line_189_861eb08e_native();
const NativeFunctionImplementation& blueprintentry_to_dict_line_231_fb4c2c3f_native();
const NativeFunctionImplementation& texturereference_to_dict_line_267_009ad0a5_native();
const NativeFunctionImplementation& materialreference_to_dict_line_300_b4f4bcee_native();
const NativeFunctionImplementation& kmapproject_mark_dirty_line_342_c3d65644_native();
const NativeFunctionImplementation& kmapproject_find_room_line_346_092336cf_native();
const NativeFunctionImplementation& kmapproject_find_module_line_349_1d605726_native();
const NativeFunctionImplementation& kmapproject_find_walkmesh_line_352_bc74da50_native();
const NativeFunctionImplementation& kmapproject_find_blueprint_line_355_58d71e76_native();
const NativeFunctionImplementation& kmapprojectmanager_construct_line_12_f38ef493_native();
const NativeFunctionImplementation& kmapprojectmanager_new_line_16_6b5c0fd8_native();
const NativeFunctionImplementation& kmapprojectmanager_open_line_21_bcb69348_native();
const NativeFunctionImplementation& kmapprojectmanager_save_line_25_23a9310b_native();
const NativeFunctionImplementation& kmapprojectmanager_save_as_line_28_da934efb_native();
const NativeFunctionImplementation& kmapvalidationissue_to_dict_line_21_125302ee_native();
const NativeFunctionImplementation& kmapvalidator_validate_line_32_740ed46c_native();
const NativeFunctionImplementation& kmapvalidator_validate_file_version_line_94_7646ced8_native();
const NativeFunctionImplementation& kmapvalidator_duplicate_ids_line_105_2b549446_native();
const NativeFunctionImplementation& levelexportbridge_construct_line_47_bc39fe48_native();
const NativeFunctionImplementation& levelexportbridge_export_fbx_line_50_26c31c6c_native();
const NativeFunctionImplementation& levelscene_add_module_line_23_e53312de_native();
const NativeFunctionImplementation& levelscene_remove_module_line_41_3071783c_native();
const NativeFunctionImplementation& levelscene_add_room_line_54_7891fdf3_native();
const NativeFunctionImplementation& levelscene_remove_room_line_79_c5b35381_native();
const NativeFunctionImplementation& levelscene_duplicate_room_line_90_b99dc1f8_native();
const NativeFunctionImplementation& levelscene_associate_walkmesh_line_110_67e30748_native();
const NativeFunctionImplementation& levelscene_add_blueprint_line_133_765063f8_native();
const NativeFunctionImplementation& levelscene_select_line_151_ee3a0ffa_native();
const NativeFunctionImplementation& levelscene_set_transform_line_157_365bd42d_native();
const NativeFunctionImplementation& levelscene_set_visibility_line_167_ece9b555_native();
const NativeFunctionImplementation& levelscene_set_locked_line_175_28f8c55a_native();
const NativeFunctionImplementation& leveltextureresolver_construct_line_12_d98b7710_native();
const NativeFunctionImplementation& leveltextureresolver_resolve_line_15_83efc1ce_native();
const NativeFunctionImplementation& leveltextureresolver_track_texture_line_27_127945bc_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::level
