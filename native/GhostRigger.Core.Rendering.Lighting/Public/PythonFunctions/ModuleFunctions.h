#pragma once

#include <cstddef>

namespace ghostrigger::core::lighting {

#ifndef GHOSTRIGGER_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& helper_cache_key_line_29_fe883150_native();
const NativeFunctionImplementation& vec3_line_15_ea1ef636_native();
const NativeFunctionImplementation& quat_line_23_9d1219b1_native();
const NativeFunctionImplementation& ordered_unique_line_86_08ee5861_native();
const NativeFunctionImplementation& int_line_168_43cff09d_native();
const NativeFunctionImplementation& positive_float_line_175_e6519143_native();
const NativeFunctionImplementation& non_negative_float_line_187_f3fc45c8_native();
const NativeFunctionImplementation& get_baked_lightmap_assignments_line_9_97e5a840_native();
const NativeFunctionImplementation& resolve_lightmap_for_material_line_23_e6e1e87d_native();
const NativeFunctionImplementation& export_baked_lightmap_manifest_line_30_134709fd_native();
const NativeFunctionImplementation& light_color_line_258_270ce3ee_native();
const NativeFunctionImplementation& intensity_line_266_a0f6c696_native();
const NativeFunctionImplementation& normalized_line_270_1d1920f5_native();
const NativeFunctionImplementation& normalized_rows_line_277_83e2c19e_native();
const NativeFunctionImplementation& world_vertices_line_163_8d640a13_native();
const NativeFunctionImplementation& world_normals_line_183_427aff6f_native();
const NativeFunctionImplementation& face_normal_line_209_707900aa_native();
const NativeFunctionImplementation& normalize_line_215_9af20a50_native();
const NativeFunctionImplementation& safe_rgb_line_222_d5ecb289_native();
const NativeFunctionImplementation& ray_triangle_line_151_095a4e62_native();
const NativeFunctionImplementation& direction_from_light_line_173_8fdb3115_native();
const NativeFunctionImplementation& uv_attr_for_channel_line_265_94958336_native();
const NativeFunctionImplementation& face_uv_attr_for_channel_line_269_f902752e_native();
const NativeFunctionImplementation& area2_line_273_5803e566_native();
const NativeFunctionImplementation& tri_world_area_line_278_3db13ea2_native();
const NativeFunctionImplementation& triangles_overlap_2d_line_288_2d9b40ea_native();
const NativeFunctionImplementation& project_line_305_48bdb73c_native();
const NativeFunctionImplementation& lerp_line_262_4a01fb4d_native();
const NativeFunctionImplementation& lerp3_line_267_4eac5829_native();
const NativeFunctionImplementation& interp3_line_275_dd2a8490_native();
const NativeFunctionImplementation& interp1_line_288_2fcde030_native();
const NativeFunctionImplementation& clamp_line_296_6765db79_native();
const NativeFunctionImplementation& make_emitter_from_node_line_633_9f489d15_native();
const NativeFunctionImplementation& build_emitter_manager_from_model_line_646_2b267f1a_native();
const NativeFunctionImplementation& build_scene_lighting_render_data_line_74_b9cc29df_native();
const NativeFunctionImplementation& light_kind_int_line_138_c4fe1262_native();
const NativeFunctionImplementation& build_light_helper_line_batches_line_154_8e565fb7_native();
const NativeFunctionImplementation& build_light_volume_line_batches_line_169_e4f01027_native();
const NativeFunctionImplementation& light_nodes_line_184_449b65be_native();
const NativeFunctionImplementation& light_from_node_line_194_3725f44a_native();
const NativeFunctionImplementation& lighting_revision_line_242_8416abf2_native();
const NativeFunctionImplementation& ambient_tuple_line_268_136d8805_native();
const NativeFunctionImplementation& vec3_line_275_75cdf5df_native();
const NativeFunctionImplementation& quat_line_283_ee250e87_native();
const NativeFunctionImplementation& color_line_291_95584596_native();
const NativeFunctionImplementation& rotate_vec_by_quat_line_296_e7f6c6ce_native();
const NativeFunctionImplementation& helper_color_line_312_c70564c4_native();
const NativeFunctionImplementation& marker_lines_line_331_efd220e4_native();
const NativeFunctionImplementation& volume_lines_line_336_a7204b92_native();
const NativeFunctionImplementation& ring_line_393_625107a8_native();
const NativeFunctionImplementation& basis_line_405_fbffbad0_native();
const NativeFunctionImplementation& v_add_line_413_9148d8d5_native();
const NativeFunctionImplementation& v_sub_line_417_8bbb1f08_native();
const NativeFunctionImplementation& v_mul_line_421_38ed9dd0_native();
const NativeFunctionImplementation& v_cross_line_425_5a3b02bc_native();
const NativeFunctionImplementation& v_norm_line_433_4e834692_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::lighting
