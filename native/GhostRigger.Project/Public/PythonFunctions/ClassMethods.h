#pragma once

#include <cstddef>

namespace ghostrigger::project {

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

const NativeFunctionImplementation& gameinstallref_from_dict_line_60_54ec3586_native();
const NativeFunctionImplementation& projectassetref_from_dict_line_88_bd98ff03_native();
const NativeFunctionImplementation& characterjobref_from_dict_line_119_8dd1da57_native();
const NativeFunctionImplementation& retargetjobref_from_dict_line_161_ae4c4c41_native();
const NativeFunctionImplementation& moduleworkspaceref_from_dict_line_200_e0d64a02_native();
const NativeFunctionImplementation& mapprojectref_from_dict_line_230_4c973cf5_native();
const NativeFunctionImplementation& scenariopackageref_from_dict_line_263_954a9b11_native();
const NativeFunctionImplementation& validationsnapshotref_from_dict_line_296_7dcf1e0a_native();
const NativeFunctionImplementation& exportcandidateref_from_dict_line_330_5423aa04_native();
const NativeFunctionImplementation& ghostriggerproject_new_line_362_903b9755_native();
const NativeFunctionImplementation& ghostriggerproject_from_dict_line_393_e2b487ff_native();
const NativeFunctionImplementation& resourceaddress_from_dict_line_87_734cf9ce_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::project
