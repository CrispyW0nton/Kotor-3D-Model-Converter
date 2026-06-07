#pragma once

#include <cstddef>

namespace ghostrigger::runtime::shared::descriptors {

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

const NativeFunctionImplementation& pivotdata_position_line_54_fa472186_native();
const NativeFunctionImplementation& pivotdata_rotation_line_62_8f4a7cea_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::runtime::shared::descriptors
