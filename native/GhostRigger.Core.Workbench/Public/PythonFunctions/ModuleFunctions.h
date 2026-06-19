#pragma once

#include <cstddef>

namespace ghostrigger::core::workbench {

#ifndef GHOSTRIGGER_WORKBENCH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WORKBENCH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WORKBENCH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& available_characters_line_60_1f913963_native();
const NativeFunctionImplementation& available_animations_line_66_edf2cf02_native();
const NativeFunctionImplementation& export_ue5_rig_line_72_822cfa1c_native();
const NativeFunctionImplementation& run_v6_export_line_130_d4575523_native();
const NativeFunctionImplementation& run_visual_validation_line_136_f8f6b44d_native();
const NativeFunctionImplementation& validate_request_line_161_bcfff5ad_native();
const NativeFunctionImplementation& collect_validation_metrics_line_180_8d036708_native();
const NativeFunctionImplementation& validation_halt_reason_line_212_29d416f7_native();
const NativeFunctionImplementation& build_workbench_manifest_line_234_6cdc88cc_native();
const NativeFunctionImplementation& write_setup_notes_line_321_beab95a6_native();
const NativeFunctionImplementation& write_json_line_407_6c7fd60b_native();
const NativeFunctionImplementation& git_commit_sha_line_411_faff249b_native();
const NativeFunctionImplementation& failure_line_426_bceea8f4_native();
const NativeFunctionImplementation& norm_line_439_d3b2dc4c_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::workbench
