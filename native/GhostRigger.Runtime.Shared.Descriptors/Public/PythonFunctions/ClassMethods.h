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

const NativeFunctionImplementation& resourceaddress_from_dict_line_87_734cf9ce_native();
const NativeFunctionImplementation& transform_from_dict_line_35_68aeedb9_native();
const NativeFunctionImplementation& pivotdata_from_dict_line_88_6fd6a9f3_native();
const NativeFunctionImplementation& sceneobjectinstance_from_dict_line_49_531c3383_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::runtime::core::host::shared::descriptors
