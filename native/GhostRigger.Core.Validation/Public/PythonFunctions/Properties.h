#pragma once

#include <cstddef>

namespace ghostrigger::core::validation {

#ifndef GHOSTRIGGER_VALIDATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_VALIDATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_VALIDATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& rawanimationfootprintreport_node_names_line_108_8ae23bc4_native();
const NativeFunctionImplementation& validationreport_has_blocking_line_85_2f48161f_native();
const NativeFunctionImplementation& validationreport_has_errors_line_89_1b4a9e00_native();
const NativeFunctionImplementation& validationreport_blocking_issues_line_93_dd1bb43c_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::validation
