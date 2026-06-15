#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::resources {

#ifndef GHOSTRIGGER_RESOURCES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RESOURCES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RESOURCES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& coerce_resource_query_line_167_aa2b5698_native();
const NativeFunctionImplementation& restype_to_extension_line_435_d168dbf6_native();
const NativeFunctionImplementation& records_from_install_line_442_29a1399c_native();
const NativeFunctionImplementation& override_records_line_460_fa1405f7_native();
const NativeFunctionImplementation& erf_records_line_484_f262248d_native();
const NativeFunctionImplementation& bif_records_line_522_923b63b9_native();
const NativeFunctionImplementation& record_line_553_2745da10_native();
const NativeFunctionImplementation& record_matches_line_585_f4a92796_native();
const NativeFunctionImplementation& sort_records_line_602_cf3d7f84_native();
const NativeFunctionImplementation& dedupe_records_line_616_788f2d14_native();
const NativeFunctionImplementation& shadow_warnings_line_628_0fd0c506_native();
const NativeFunctionImplementation& missing_message_line_639_8fea0f4d_native();
const NativeFunctionImplementation& safe_path_size_line_645_ca4cce06_native();
const NativeFunctionImplementation& clean_text_line_654_ba113744_native();
const NativeFunctionImplementation& clean_restype_line_663_96e19284_native();
const NativeFunctionImplementation& clean_game_line_672_dc0cf339_native();
const NativeFunctionImplementation& manager_game_name_line_684_d824b250_native();
const NativeFunctionImplementation& manager_install_line_688_f11c7825_native();
const NativeFunctionImplementation& resource_manager_type_id_line_696_88dd7962_native();
const NativeFunctionImplementation& resource_manager_restype_line_706_feb4e7a7_native();
const NativeFunctionImplementation& known_resource_type_ids_line_715_dd065008_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::resources
