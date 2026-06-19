#pragma once

#include <cstddef>

namespace ghostrigger::core::diagnostics {

#ifndef GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_DIAGNOSTICS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& modulereferencesafetyreport_blocking_issues_line_115_171f31df_native();
const NativeFunctionImplementation& validationissue_is_error_line_89_7a815511_native();
const NativeFunctionImplementation& validationissue_is_warning_line_93_c018c090_native();
const NativeFunctionImplementation& validationservice_errors_line_217_b51ddb1a_native();
const NativeFunctionImplementation& validationservice_warnings_line_221_93dcf42f_native();
const NativeFunctionImplementation& validationservice_passed_line_225_a1d15a36_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::diagnostics
