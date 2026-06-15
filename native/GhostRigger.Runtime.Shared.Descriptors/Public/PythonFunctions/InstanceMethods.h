#pragma once

#include <cstddef>

namespace ghostrigger::runtime::core::host::shared::descriptors {

#ifndef GHOSTRIGGER_RUNTIME_SHARED_DESCRIPTORS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RUNTIME_SHARED_DESCRIPTORS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RUNTIME_SHARED_DESCRIPTORS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& resourceaddress_post_construct_line_57_2af13706_native();
const NativeFunctionImplementation& resourceaddress_to_dict_line_72_4e4775e5_native();
const NativeFunctionImplementation& resourceaddress_stable_key_line_105_f62055fd_native();
const NativeFunctionImplementation& resourceaddress_display_name_line_147_9fa30e20_native();
const NativeFunctionImplementation& transform_to_dict_line_27_0e4c5c8d_native();
const NativeFunctionImplementation& pivotdata_position_line_58_a41b1041_native();
const NativeFunctionImplementation& pivotdata_rotation_line_66_052837bd_native();
const NativeFunctionImplementation& pivotdata_is_valid_line_69_52cd01cc_native();
const NativeFunctionImplementation& pivotdata_sanitized_line_73_9bbd75d0_native();
const NativeFunctionImplementation& pivotdata_to_dict_line_78_3048ea00_native();
const NativeFunctionImplementation& sceneobjectinstance_to_dict_line_27_564c9705_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::runtime::core::host::shared::descriptors
