#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_sequence {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_sequence_sequence_asset_inspect_sequence_asset_line_24_9dc7218d_descriptor_json();
const char* src_sequence_sequence_evaluator_vec3_line_24_4114c5a2_descriptor_json();
const char* src_sequence_sequence_evaluator_quat_line_32_50d74e5d_descriptor_json();
const char* src_sequence_sequence_interpolation_ease_line_11_a760953f_descriptor_json();
const char* src_sequence_sequence_interpolation_lerp_number_line_22_fb55d093_descriptor_json();
const char* src_sequence_sequence_interpolation_interpolate_values_line_26_d369775d_descriptor_json();
const char* src_sequence_sequence_interpolation_evaluate_keyframes_line_59_1110b1b0_descriptor_json();
const char* src_sequence_sequence_manager_ensure_sequence_object_id_line_16_57d9eb8d_descriptor_json();
const char* src_sequence_sequence_manager_infer_target_type_line_36_fa8d664b_descriptor_json();
const char* src_sequence_sequence_model_utc_now_iso_line_17_86773d91_descriptor_json();
const char* src_sequence_sequence_model_validate_frame_rate_line_57_0072f6d4_descriptor_json();
const char* src_sequence_sequence_serialization_sequence_to_json_line_19_1aef18d8_descriptor_json();
const char* src_sequence_sequence_serialization_sequence_from_json_line_23_c40978d0_descriptor_json();
const char* src_sequence_sequence_serialization_save_sequence_file_line_31_db800667_descriptor_json();
const char* src_sequence_sequence_serialization_load_sequence_file_line_45_6dee483d_descriptor_json();
const char* src_sequence_sequence_track_register_track_line_16_585a4ce8_descriptor_json();
const char* src_sequence_tracks_transform_track_transform_value_line_12_607baaf2_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_sequence
