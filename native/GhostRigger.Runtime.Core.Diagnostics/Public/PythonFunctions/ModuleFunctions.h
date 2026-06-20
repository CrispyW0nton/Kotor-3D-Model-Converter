#pragma once

#include <cstddef>

namespace ghostrigger::core::diagnostics {

#ifndef GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& set_sentinel_dir_line_44_8ae827ec_native();
const NativeFunctionImplementation& log_mdl_header_line_55_555985b6_native();
const NativeFunctionImplementation& validate_mdl_preconditions_line_141_b19c0b38_native();
const NativeFunctionImplementation& load_timer_line_184_838b14f5_native();
const NativeFunctionImplementation& log_model_summary_line_210_51f13b57_native();
const NativeFunctionImplementation& log_model_anomalies_line_260_d81498cb_native();
const NativeFunctionImplementation& log_render_error_line_355_8784dfa8_native();
const NativeFunctionImplementation& check_main_thread_line_390_c935d866_native();
const NativeFunctionImplementation& log_thread_violation_line_406_d1d6f04c_native();
const NativeFunctionImplementation& log_texture_resolution_line_424_15424580_native();
const NativeFunctionImplementation& log_crash_report_line_456_4d715750_native();
const NativeFunctionImplementation& write_crash_sentinel_line_517_62a85bcd_native();
const NativeFunctionImplementation& run_model_diagnostics_line_545_133f9b6e_native();
const NativeFunctionImplementation& log_session_start_line_678_715dbbf7_native();
const NativeFunctionImplementation& report_old_sentinels_line_717_8dd23cec_native();
const NativeFunctionImplementation& module_from_input_line_119_8faf9ef8_native();
const NativeFunctionImplementation& normalise_resref_line_123_5bfdaeb7_native();
const NativeFunctionImplementation& normalise_restype_line_132_5c829799_native();
const NativeFunctionImplementation& record_key_line_136_d01ddfdd_native();
const NativeFunctionImplementation& resources_from_input_line_149_50bc7de0_native();
const NativeFunctionImplementation& available_index_line_162_9dfee9c1_native();
const NativeFunctionImplementation& git_raw_line_196_a688d5a0_native();
const NativeFunctionImplementation& core_raw_line_203_6ab0a473_native();
const NativeFunctionImplementation& raw_list_line_213_a7111a0b_native();
const NativeFunctionImplementation& script_field_line_221_fa440c9a_native();
const NativeFunctionImplementation& dialog_field_line_226_58535f64_native();
const NativeFunctionImplementation& iter_script_dialog_refs_line_230_de4ac179_native();
const NativeFunctionImplementation& collect_module_references_line_260_b7f6bfe1_native();
const NativeFunctionImplementation& has_reference_line_291_462c6d98_native();
const NativeFunctionImplementation& issue_for_missing_line_309_e4fe892b_native();
const NativeFunctionImplementation& validate_module_references_line_344_44437eb2_native();
const NativeFunctionImplementation& validate_scene_line_462_4978dd75_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::diagnostics
