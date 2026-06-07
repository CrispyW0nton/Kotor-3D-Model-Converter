#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_project {

const char* src_core_project_project_validation_projectvalidationreport_has_blocking_line_47_fcc20675_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Project","python_module":"src.core.project.project_validation","python_file":"src/core/project/project_validation.py","qualname":"ProjectValidationReport.has_blocking","name":"has_blocking","kind":"properties","line":47,"end_line":48,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_core_project_project_validation_projectvalidationreport_blocking_issues_line_51_cdb60b7e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Project","python_module":"src.core.project.project_validation","python_file":"src/core/project/project_validation.py","qualname":"ProjectValidationReport.blocking_issues","name":"blocking_issues","kind":"properties","line":51,"end_line":52,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/project/project_validation.py", "ProjectValidationReport.has_blocking", "properties", &src_core_project_project_validation_projectvalidationreport_has_blocking_line_47_fcc20675_descriptor_json},
        {"src/core/project/project_validation.py", "ProjectValidationReport.blocking_issues", "properties", &src_core_project_project_validation_projectvalidationreport_blocking_issues_line_51_cdb60b7e_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_project
