#pragma once

#include <cstddef>

namespace ghostrigger::kotormcp {

#ifndef GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& debugsession_load_model_depth_line_288_7527285a_native();
const NativeFunctionImplementation& debugsession_get_bone_hierarchy_build_tree_line_606_3daacf2b_native();
const NativeFunctionImplementation& close_quat_close_line_104_b36abb8a_native();
const NativeFunctionImplementation& compare_model_pipelines_add_line_261_5b32c5d1_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::kotormcp
