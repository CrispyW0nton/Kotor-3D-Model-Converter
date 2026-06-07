#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_diagnostics {

const char* src_core_diagnostics_module_reference_safety_modulereferencesafetyreport_blocking_issues_line_115_171f31df_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Diagnostics","python_module":"src.core.diagnostics.module_reference_safety","python_file":"src/core/diagnostics/module_reference_safety.py","qualname":"ModuleReferenceSafetyReport.blocking_issues","name":"blocking_issues","kind":"properties","line":115,"end_line":116,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_diagnostics_validation_service_validationissue_is_error_line_89_7a815511_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Diagnostics","python_module":"src.core.diagnostics.validation_service","python_file":"src/core/diagnostics/validation_service.py","qualname":"ValidationIssue.is_error","name":"is_error","kind":"properties","line":89,"end_line":90,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_diagnostics_validation_service_validationissue_is_warning_line_93_c018c090_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Diagnostics","python_module":"src.core.diagnostics.validation_service","python_file":"src/core/diagnostics/validation_service.py","qualname":"ValidationIssue.is_warning","name":"is_warning","kind":"properties","line":93,"end_line":94,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_diagnostics_validation_service_validationservice_errors_line_217_b51ddb1a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Diagnostics","python_module":"src.core.diagnostics.validation_service","python_file":"src/core/diagnostics/validation_service.py","qualname":"ValidationService.errors","name":"errors","kind":"properties","line":217,"end_line":218,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_diagnostics_validation_service_validationservice_warnings_line_221_93dcf42f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Diagnostics","python_module":"src.core.diagnostics.validation_service","python_file":"src/core/diagnostics/validation_service.py","qualname":"ValidationService.warnings","name":"warnings","kind":"properties","line":221,"end_line":222,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_diagnostics_validation_service_validationservice_passed_line_225_a1d15a36_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Diagnostics","python_module":"src.core.diagnostics.validation_service","python_file":"src/core/diagnostics/validation_service.py","qualname":"ValidationService.passed","name":"passed","kind":"properties","line":225,"end_line":227,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/diagnostics/module_reference_safety.py", "ModuleReferenceSafetyReport.blocking_issues", "properties", &src_core_diagnostics_module_reference_safety_modulereferencesafetyreport_blocking_issues_line_115_171f31df_descriptor_json},
        {"src/core/diagnostics/validation_service.py", "ValidationIssue.is_error", "properties", &src_core_diagnostics_validation_service_validationissue_is_error_line_89_7a815511_descriptor_json},
        {"src/core/diagnostics/validation_service.py", "ValidationIssue.is_warning", "properties", &src_core_diagnostics_validation_service_validationissue_is_warning_line_93_c018c090_descriptor_json},
        {"src/core/diagnostics/validation_service.py", "ValidationService.errors", "properties", &src_core_diagnostics_validation_service_validationservice_errors_line_217_b51ddb1a_descriptor_json},
        {"src/core/diagnostics/validation_service.py", "ValidationService.warnings", "properties", &src_core_diagnostics_validation_service_validationservice_warnings_line_221_93dcf42f_descriptor_json},
        {"src/core/diagnostics/validation_service.py", "ValidationService.passed", "properties", &src_core_diagnostics_validation_service_validationservice_passed_line_225_a1d15a36_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_diagnostics
