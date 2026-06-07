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

const NativeFunctionImplementation& basemodel_model_validate_line_23_d78d3b93_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::kotormcp
