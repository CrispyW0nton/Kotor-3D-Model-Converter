#pragma once

#include <cstddef>

namespace ghostrigger::core::project {

#ifndef GHOSTRIGGER_PROJECT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_PROJECT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_PROJECT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& gameinstallref_to_dict_line_56_1ba1f16c_native();
const NativeFunctionImplementation& projectassetref_to_dict_line_78_dd89ca66_native();
const NativeFunctionImplementation& characterjobref_to_dict_line_108_b723bdcd_native();
const NativeFunctionImplementation& retargetjobref_to_dict_line_145_540c738e_native();
const NativeFunctionImplementation& moduleworkspaceref_to_dict_line_189_9eb5183d_native();
const NativeFunctionImplementation& mapprojectref_to_dict_line_220_8896c56b_native();
const NativeFunctionImplementation& scenariopackageref_to_dict_line_251_6cccf42c_native();
const NativeFunctionImplementation& validationsnapshotref_to_dict_line_285_34d9f19a_native();
const NativeFunctionImplementation& exportcandidateref_to_dict_line_318_a6f258b5_native();
const NativeFunctionImplementation& ghostriggerproject_to_dict_line_372_e2a5fcfe_native();
const NativeFunctionImplementation& projectvalidationissue_to_dict_line_31_34d795ee_native();
const NativeFunctionImplementation& projectvalidationreport_add_line_54_6a5e00e7_native();
const NativeFunctionImplementation& resourceaddress_post_construct_line_57_2af13706_native();
const NativeFunctionImplementation& resourceaddress_to_dict_line_72_4e4775e5_native();
const NativeFunctionImplementation& resourceaddress_stable_key_line_105_f62055fd_native();
const NativeFunctionImplementation& resourceaddress_display_name_line_147_9fa30e20_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::project
