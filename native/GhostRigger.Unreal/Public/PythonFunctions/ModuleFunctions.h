#pragma once

#include <cstddef>

namespace ghostrigger::unreal {

#ifndef GHOSTRIGGER_UNREAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_UNREAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_UNREAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& is_null_helper_name_line_65_0343b175_native();
const NativeFunctionImplementation& is_kotor_mesh_bone_name_line_70_18280a53_native();
const NativeFunctionImplementation& nodes_by_name_line_129_f8a1d6a2_native();
const NativeFunctionImplementation& target_nodes_line_138_3bc52421_native();
const NativeFunctionImplementation& node_key_line_142_a22e38f5_native();
const NativeFunctionImplementation& is_skeletal_node_line_146_e1060f45_native();
const NativeFunctionImplementation& candidate_names_line_161_90a4b08e_native();
const NativeFunctionImplementation& clean_manual_mapping_line_173_e06b1f6c_native();
const NativeFunctionImplementation& build_bone_map_line_185_ac179881_native();
const NativeFunctionImplementation& sub3_line_246_16ce312d_native();
const NativeFunctionImplementation& add3_line_254_91675499_native();
const NativeFunctionImplementation& mul3_line_262_4ee118d9_native();
const NativeFunctionImplementation& sub_quat_line_266_ec3bf51c_native();
const NativeFunctionImplementation& normal_quat_line_270_288f4168_native();
const NativeFunctionImplementation& quat_conjugate_line_278_89858516_native();
const NativeFunctionImplementation& quat_mul_line_283_389ecdd2_native();
const NativeFunctionImplementation& retarget_rotation_line_294_a81a4bfb_native();
const NativeFunctionImplementation& slerp_quat_line_300_12f988b5_native();
const NativeFunctionImplementation& bind_pose_line_330_fbbe736a_native();
const NativeFunctionImplementation& world_positions_by_key_line_340_8108eecc_native();
const NativeFunctionImplementation& height_from_positions_line_363_3c65168f_native();
const NativeFunctionImplementation& position_delta_scale_line_370_abf8e5e9_native();
const NativeFunctionImplementation& nearest_direct_ancestor_line_393_ce66872b_native();
const NativeFunctionImplementation& path_from_ancestor_to_node_line_402_83e81fe8_native();
const NativeFunctionImplementation& apply_bridge_poses_line_414_522eba82_native();
const NativeFunctionImplementation& derived_target_bone_keys_line_478_60e92136_native();
const NativeFunctionImplementation& retarget_pose_line_505_27943e98_native();
const NativeFunctionImplementation& sample_retargeted_animation_line_584_3d21611c_native();
const NativeFunctionImplementation& scaled_position_values_line_662_401176f4_native();
const NativeFunctionImplementation& copy_retargeted_animation_line_674_c77e5569_native();
const NativeFunctionImplementation& retarget_animation_line_721_a8425bc0_native();
const NativeFunctionImplementation& fbx_clean_name_line_68_1d924e3e_native();
const NativeFunctionImplementation& fbx_child_value_line_72_620c744d_native();
const NativeFunctionImplementation& fbx_property70_line_79_4d1cc41a_native();
const NativeFunctionImplementation& quat_mul_xyzw_line_89_d1158bda_native();
const NativeFunctionImplementation& axis_angle_quat_line_100_e70e34c4_native();
const NativeFunctionImplementation& euler_xyz_to_quat_line_111_b1755802_native();
const NativeFunctionImplementation& yaw_180_point_line_124_d72a9d8d_native();
const NativeFunctionImplementation& fbx_model_lookup_line_128_f1fbc578_native();
const NativeFunctionImplementation& fbx_parent_map_line_141_5a8fc22f_native();
const NativeFunctionImplementation& fbx_children_map_line_154_127fa53c_native();
const NativeFunctionImplementation& infer_unreal_bone_side_line_165_2d5c54cc_native();
const NativeFunctionImplementation& infer_unreal_bone_group_line_174_be0ba3b4_native();
const NativeFunctionImplementation& infer_unreal_bone_role_line_189_37d9af3a_native();
const NativeFunctionImplementation& fbx_skeleton_bones_line_200_b723d6b0_native();
const NativeFunctionImplementation& build_fbx_skeleton_model_line_227_7c1a13b4_native();
const NativeFunctionImplementation& read_fbx_property_line_313_ff8c4d3e_native();
const NativeFunctionImplementation& read_fbx_node_line_360_264d7cbe_native();
const NativeFunctionImplementation& read_binary_fbx_line_391_4944b6ed_native();
const NativeFunctionImplementation& fbx_object_texture_names_line_408_08402480_native();
const NativeFunctionImplementation& fbx_geometry_to_mesh_node_line_442_beda15df_native();
const NativeFunctionImplementation& fbx_apply_skinning_line_529_a1ca7eca_native();
const NativeFunctionImplementation& load_unreal_bone_map_line_609_0a8e4248_native();
const NativeFunctionImplementation& load_quinn_skeleton_asset_line_637_b6f165fc_native();
const NativeFunctionImplementation& unreal_skeleton_model_line_660_14c9dfde_native();
const NativeFunctionImplementation& load_quinn_fbx_model_line_685_8be13da8_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::unreal
