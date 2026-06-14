#include "PythonFunctions/Properties.h"

namespace ghostrigger::domain::core::project {

const NativeFunctionImplementation& projectvalidationreport_has_blocking_line_47_fcc20675_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Project",
        "ghostrigger::domain::core::project::core::project::project_validation",
        "src/core/project/project_validation.py",
        "ProjectValidationReport.has_blocking",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Project","namespace":"ghostrigger::domain::core::project::core::project::project_validation","python_file":"src/core/project/project_validation.py","qualname":"ProjectValidationReport.has_blocking","name":"has_blocking","callable_type":"properties","line":47,"end_line":48,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& projectvalidationreport_blocking_issues_line_51_cdb60b7e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Project",
        "ghostrigger::domain::core::project::core::project::project_validation",
        "src/core/project/project_validation.py",
        "ProjectValidationReport.blocking_issues",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Project","namespace":"ghostrigger::domain::core::project::core::project::project_validation","python_file":"src/core/project/project_validation.py","qualname":"ProjectValidationReport.blocking_issues","name":"blocking_issues","callable_type":"properties","line":51,"end_line":52,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        projectvalidationreport_has_blocking_line_47_fcc20675_native(),
        projectvalidationreport_blocking_issues_line_51_cdb60b7e_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::project
