#pragma once

#include <cstddef>

namespace ghostrigger::core::retargeting {

#ifndef GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RETARGETING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& validate_ground_truth_visit_line_422_084fe0e3_native();
const NativeFunctionImplementation& topological_nodes_visit_line_526_fc7691aa_native();
const NativeFunctionImplementation& export_retarget_preview_override_writer_line_112_f70d9a3b_native();
const NativeFunctionImplementation& export_retarget_preview_override_verifier_line_151_ace060b3_native();
const NativeFunctionImplementation& topological_sort_visit_line_122_cfa7e074_native();
const NativeFunctionImplementation& align_target_skeleton_to_source_record_line_318_919b9ae6_native();
const NativeFunctionImplementation& check_acyclic_visit_line_146_a9d75fe8_native();
const NativeFunctionImplementation& export_kotor_to_unreal_preview_writer_line_77_4312eaa2_native();
const NativeFunctionImplementation& export_kotor_to_unreal_preview_verifier_line_87_9a6ab22b_native();
const NativeFunctionImplementation& export_kotor_to_unreal_preview_manifest_writer_line_101_467a4d6c_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::retargeting
