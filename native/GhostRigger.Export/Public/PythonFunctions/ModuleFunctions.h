#pragma once

#include <cstddef>

namespace ghostrigger::export_ {

#ifndef GHOSTRIGGER_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_EXPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& run_export_job_line_108_e68b41e9_native();
const NativeFunctionImplementation& preflight_export_request_line_263_01b4bba5_native();
const NativeFunctionImplementation& validate_staged_outputs_line_319_8e66a640_native();
const NativeFunctionImplementation& result_line_334_e9ef6bd5_native();
const NativeFunctionImplementation& single_issue_report_line_362_5757b4ff_native();
const NativeFunctionImplementation& issue_line_385_4db8c74f_native();
const NativeFunctionImplementation& publish_line_401_a53a92e7_native();
const NativeFunctionImplementation& shared_output_parent_line_413_001c658b_native();
const NativeFunctionImplementation& rollback_promoted_outputs_line_422_6cf28be4_native();
const NativeFunctionImplementation& final_manifest_path_line_439_188f8463_native();
const NativeFunctionImplementation& normalized_path_key_line_446_7fbdeaec_native();
const NativeFunctionImplementation& safe_job_id_line_450_e73ab220_native();
const NativeFunctionImplementation& ensure_json_serializable_line_455_dc882db9_native();
const NativeFunctionImplementation& decode_accessor_line_152_6f438c5e_native();
const NativeFunctionImplementation& resolve_buffers_line_231_3b6565af_native();
const NativeFunctionImplementation& matrix_to_trs_line_265_79964a2c_native();
const NativeFunctionImplementation& node_trs_from_mapping_line_318_b07a17f5_native();
const NativeFunctionImplementation& node_scale_from_mapping_line_333_5454ffdb_native();
const NativeFunctionImplementation& node_trs_from_object_line_346_bdd95aaa_native();
const NativeFunctionImplementation& node_scale_from_object_line_361_ddbf387c_native();
const NativeFunctionImplementation& mul_scale_line_369_72dca566_native();
const NativeFunctionImplementation& apply_scale_to_pos_line_376_1219d937_native();
const NativeFunctionImplementation& compose_gltf_world_line_383_c0f9e7e1_native();
const NativeFunctionImplementation& gltf_root_indices_line_400_1b3f99ac_native();
const NativeFunctionImplementation& candidate_blender_executables_line_1082_aaa33477_native();
const NativeFunctionImplementation& blender_sort_key_line_1125_18a02b8a_native();
const NativeFunctionImplementation& convert_fbx_to_glb_with_blender_line_1136_428ff1fd_native();
const NativeFunctionImplementation& auto_import_line_1184_b404afc0_native();
const NativeFunctionImplementation& build_skin_data_line_1215_fcd8f9f0_native();
const NativeFunctionImplementation& channel_to_controller_line_1238_6e25f4a7_native();
const NativeFunctionImplementation& fill_material_pygltflib_line_1258_6367fccf_native();
const NativeFunctionImplementation& asset_relative_line_18_5ce50433_native();
const NativeFunctionImplementation& build_output_paths_line_27_18384c92_native();
const NativeFunctionImplementation& summarize_model_line_41_3b22d89c_native();
const NativeFunctionImplementation& inspect_fbx_skin_objects_line_85_bdc78f34_native();
const NativeFunctionImplementation& export_model_for_unity_line_159_63d8706b_native();
const NativeFunctionImplementation& as_list_line_10_902fc7b4_native();
const NativeFunctionImplementation& clip_name_line_20_8f3b8c4f_native();
const NativeFunctionImplementation& renderer_type_line_28_e82cbec7_native();
const NativeFunctionImplementation& renderer_int_line_36_b33aab39_native();
const NativeFunctionImplementation& material_count_line_48_9d6865dc_native();
const NativeFunctionImplementation& build_unity_import_manifest_line_61_0bc29d4a_native();
const NativeFunctionImplementation& validate_unity_import_file_line_180_e7e3ce03_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::export_
