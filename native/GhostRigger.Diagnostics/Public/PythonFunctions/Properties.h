#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_diagnostics {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_diagnostics_module_reference_safety_modulereferencesafetyreport_blocking_issues_line_115_171f31df_descriptor_json();
const char* src_core_diagnostics_validation_service_validationissue_is_error_line_89_7a815511_descriptor_json();
const char* src_core_diagnostics_validation_service_validationissue_is_warning_line_93_c018c090_descriptor_json();
const char* src_core_diagnostics_validation_service_validationservice_errors_line_217_b51ddb1a_descriptor_json();
const char* src_core_diagnostics_validation_service_validationservice_warnings_line_221_93dcf42f_descriptor_json();
const char* src_core_diagnostics_validation_service_validationservice_passed_line_225_a1d15a36_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_diagnostics
