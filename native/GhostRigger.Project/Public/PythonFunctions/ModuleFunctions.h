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

const NativeFunctionImplementation& utc_now_iso_line_19_f56c2155_native();
const NativeFunctionImplementation& stable_project_id_line_23_7a314c4a_native();
const NativeFunctionImplementation& dict_line_27_05502939_native();
const NativeFunctionImplementation& address_or_none_line_31_e1291f2f_native();
const NativeFunctionImplementation& address_to_dict_line_37_7a27551c_native();
const NativeFunctionImplementation& addresses_from_list_line_41_12888262_native();
const NativeFunctionImplementation& addresses_to_list_line_45_8d494fb6_native();
const NativeFunctionImplementation& save_ghostrigger_project_line_431_68be8512_native();
const NativeFunctionImplementation& load_ghostrigger_project_line_442_87956209_native();
const NativeFunctionImplementation& json_issue_line_76_c4c51223_native();
const NativeFunctionImplementation& require_line_90_c6a6e140_native();
const NativeFunctionImplementation& validate_resource_address_line_95_47324977_native();
const NativeFunctionImplementation& validate_ghostrigger_project_line_146_1d5d45bd_native();
const NativeFunctionImplementation& validate_resref_line_240_cc257424_native();
const NativeFunctionImplementation& validate_duplicate_ids_line_269_5216a590_native();
const NativeFunctionImplementation& append_json_issue_line_289_343a3960_native();
const NativeFunctionImplementation& validate_address_field_line_295_196f1665_native();
const NativeFunctionImplementation& validate_optional_address_field_line_307_255a9d07_native();
const NativeFunctionImplementation& validate_address_list_line_317_9a2cac4f_native();
const NativeFunctionImplementation& validate_export_candidate_line_327_6f5d7247_native();
const NativeFunctionImplementation& clean_optional_text_line_25_9d764858_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::project
