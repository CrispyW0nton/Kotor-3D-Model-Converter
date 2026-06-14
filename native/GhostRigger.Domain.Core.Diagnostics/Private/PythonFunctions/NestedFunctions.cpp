#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::domain::core::diagnostics {

const NativeFunctionImplementation& run_model_diagnostics_emit_line_567_9da1a4d8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Diagnostics",
        "ghostrigger::domain::core::diagnostics::core::diagnostics::diagnostics",
        "src/core/diagnostics/diagnostics.py",
        "run_model_diagnostics.emit",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Diagnostics","namespace":"ghostrigger::domain::core::diagnostics::core::diagnostics::diagnostics","python_file":"src/core/diagnostics/diagnostics.py","qualname":"run_model_diagnostics.emit","name":"emit","callable_type":"nested_functions","line":567,"end_line":574,"signature":{"args":["msg","level"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& available_index_add_line_165_1e892e06_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Diagnostics",
        "ghostrigger::domain::core::diagnostics::core::diagnostics::module_reference_safety",
        "src/core/diagnostics/module_reference_safety.py",
        "_available_index._add",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Diagnostics","namespace":"ghostrigger::domain::core::diagnostics::core::diagnostics::module_reference_safety","python_file":"src/core/diagnostics/module_reference_safety.py","qualname":"_available_index._add","name":"_add","callable_type":"nested_functions","line":165,"end_line":169,"signature":{"args":["resref","restype"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        run_model_diagnostics_emit_line_567_9da1a4d8_native(),
        available_index_add_line_165_1e892e06_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::diagnostics
