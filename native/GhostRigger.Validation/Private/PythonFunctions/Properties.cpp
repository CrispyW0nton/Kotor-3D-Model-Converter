#include "PythonFunctions/Properties.h"

namespace ghostrigger::validation {

const NativeFunctionImplementation& rawanimationfootprintreport_node_names_line_108_8ae23bc4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Validation",
        "ghostrigger::validation::core::validation::animation_block_validator",
        "src/core/validation/animation_block_validator.py",
        "RawAnimationFootprintReport.node_names",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Validation","namespace":"ghostrigger::validation::core::validation::animation_block_validator","python_file":"src/core/validation/animation_block_validator.py","qualname":"RawAnimationFootprintReport.node_names","name":"node_names","callable_type":"properties","line":108,"end_line":109,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& validationreport_has_blocking_line_85_2f48161f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Validation",
        "ghostrigger::validation::core::validation::validation_bus",
        "src/core/validation/validation_bus.py",
        "ValidationReport.has_blocking",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Validation","namespace":"ghostrigger::validation::core::validation::validation_bus","python_file":"src/core/validation/validation_bus.py","qualname":"ValidationReport.has_blocking","name":"has_blocking","callable_type":"properties","line":85,"end_line":86,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& validationreport_has_errors_line_89_1b4a9e00_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Validation",
        "ghostrigger::validation::core::validation::validation_bus",
        "src/core/validation/validation_bus.py",
        "ValidationReport.has_errors",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Validation","namespace":"ghostrigger::validation::core::validation::validation_bus","python_file":"src/core/validation/validation_bus.py","qualname":"ValidationReport.has_errors","name":"has_errors","callable_type":"properties","line":89,"end_line":90,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& validationreport_blocking_issues_line_93_dd1bb43c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Validation",
        "ghostrigger::validation::core::validation::validation_bus",
        "src/core/validation/validation_bus.py",
        "ValidationReport.blocking_issues",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Validation","namespace":"ghostrigger::validation::core::validation::validation_bus","python_file":"src/core/validation/validation_bus.py","qualname":"ValidationReport.blocking_issues","name":"blocking_issues","callable_type":"properties","line":93,"end_line":94,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        rawanimationfootprintreport_node_names_line_108_8ae23bc4_native(),
        validationreport_has_blocking_line_85_2f48161f_native(),
        validationreport_has_errors_line_89_1b4a9e00_native(),
        validationreport_blocking_issues_line_93_dd1bb43c_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::validation
