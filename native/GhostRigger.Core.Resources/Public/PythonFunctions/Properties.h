#pragma once

#include <cstddef>

namespace ghostrigger::core::resources {

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

const NativeFunctionImplementation& gameresourcerecord_resref_line_116_3d616c56_native();
const NativeFunctionImplementation& gameresourcerecord_restype_line_120_1d46f82f_native();
const NativeFunctionImplementation& gameresourcerecord_layer_line_124_3bab406c_native();
const NativeFunctionImplementation& gameresourcerecord_key_line_128_f409ca4e_native();
const NativeFunctionImplementation& gameresourceresult_address_line_147_0e30bfb9_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::resources
