#pragma once

#include <cstddef>

namespace ghostrigger::runtime::shared::contracts {

#ifndef GHOSTRIGGER_RUNTIME_SHARED_CONTRACTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RUNTIME_SHARED_CONTRACTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RUNTIME_SHARED_CONTRACTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& repo_root_line_664_6b579e67_native();
const NativeFunctionImplementation& candidate_paths_line_668_f7698985_native();
const NativeFunctionImplementation& decode_json_line_681_c57c56f2_native();
const NativeFunctionImplementation& cpu_skinning_fallback_batch_item_to_dict_line_2301_c912dd2d_native();
const NativeFunctionImplementation& gpu_skinning_dispatch_item_to_dict_line_2317_1641aa65_native();
const NativeFunctionImplementation& resource_upload_item_to_dict_line_2330_e0df7076_native();
const NativeFunctionImplementation& device_resource_item_to_dict_line_2343_e563a16f_native();
const NativeFunctionImplementation& device_resource_upload_commit_item_to_dict_line_2357_3561c33e_native();
const NativeFunctionImplementation& device_resource_transition_item_to_dict_line_2367_2441bd93_native();
const NativeFunctionImplementation& draw_item_to_dict_line_2379_c431326f_native();
const NativeFunctionImplementation& draw_batch_to_dict_line_2391_5c57f3e4_native();
const NativeFunctionImplementation& vec3_line_2402_56084119_native();
const NativeFunctionImplementation& vec4_line_2409_62260cb6_native();
const NativeFunctionImplementation& flatten_matrices_line_2416_35af63bb_native();
const NativeFunctionImplementation& flatten_transform_matrix_line_2438_9cea9dfc_native();
const NativeFunctionImplementation& flatten_positions_line_2457_0bcbec57_native();
const NativeFunctionImplementation& flatten_indices_line_2480_ecd95aee_native();
const NativeFunctionImplementation& flatten_skin_indices_line_2493_911ca48c_native();
const NativeFunctionImplementation& flatten_skin_weights_line_2498_78ccf10b_native();
const NativeFunctionImplementation& flatten_matrix_like_line_2503_f898edc6_native();
const NativeFunctionImplementation& flatten_numeric_line_2526_8e5122e0_native();
const NativeFunctionImplementation& texture_bytes_line_2539_6cf97f46_native();
const NativeFunctionImplementation& safe_len_line_875_2b260a11_native();
const NativeFunctionImplementation& material_slot_line_886_8b4e8754_native();
const NativeFunctionImplementation& mesh_flags_line_894_b4ae071b_native();
const NativeFunctionImplementation& material_color_line_906_28e11dac_native();
const NativeFunctionImplementation& mesh_bounds_line_923_45af63f7_native();
const NativeFunctionImplementation& frame_flags_line_960_3d801e42_native();
const NativeFunctionImplementation& pick_ray_from_request_line_973_841d79ad_native();
const NativeFunctionImplementation& vec3_line_986_da54c03f_native();
const NativeFunctionImplementation& texture_key_line_993_1fc5daf0_native();
const NativeFunctionImplementation& texture_size_line_1001_0591e482_native();
const NativeFunctionImplementation& texture_byte_size_line_1015_f6e27853_native();
const NativeFunctionImplementation& texture_format_line_1032_b2b58131_native();
const NativeFunctionImplementation& texture_flags_line_1040_8f25e810_native();
const NativeFunctionImplementation& texture_payload_line_1049_e8478aed_native();
const NativeFunctionImplementation& texture_row_pitch_line_1068_087037f2_native();
const NativeFunctionImplementation& stable_clip_hash_line_1078_2e4c8ef1_native();
const NativeFunctionImplementation& normalize_renderer_backend_line_66_6420bbbf_native();
const NativeFunctionImplementation& supported_renderer_backend_line_73_e099ca56_native();
const NativeFunctionImplementation& renderer_backend_label_line_80_7ea56790_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::runtime::shared::contracts
