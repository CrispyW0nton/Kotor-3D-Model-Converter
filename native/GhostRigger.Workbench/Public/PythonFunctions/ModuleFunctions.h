#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_workbench {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_workbench_ue5_rig_export_available_characters_line_60_1f913963_descriptor_json();
const char* src_workbench_ue5_rig_export_available_animations_line_66_edf2cf02_descriptor_json();
const char* src_workbench_ue5_rig_export_export_ue5_rig_line_72_822cfa1c_descriptor_json();
const char* src_workbench_ue5_rig_export_run_v6_export_line_130_d4575523_descriptor_json();
const char* src_workbench_ue5_rig_export_run_visual_validation_line_136_f8f6b44d_descriptor_json();
const char* src_workbench_ue5_rig_export_validate_request_line_161_bcfff5ad_descriptor_json();
const char* src_workbench_ue5_rig_export_collect_validation_metrics_line_180_8d036708_descriptor_json();
const char* src_workbench_ue5_rig_export_validation_halt_reason_line_212_29d416f7_descriptor_json();
const char* src_workbench_ue5_rig_export_build_workbench_manifest_line_234_6cdc88cc_descriptor_json();
const char* src_workbench_ue5_rig_export_write_setup_notes_line_321_beab95a6_descriptor_json();
const char* src_workbench_ue5_rig_export_write_json_line_407_6c7fd60b_descriptor_json();
const char* src_workbench_ue5_rig_export_git_commit_sha_line_411_faff249b_descriptor_json();
const char* src_workbench_ue5_rig_export_failure_line_426_bceea8f4_descriptor_json();
const char* src_workbench_ue5_rig_export_norm_line_439_d3b2dc4c_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_workbench
