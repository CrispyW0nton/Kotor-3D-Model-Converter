#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::tools::workflow::pivotcontrols {

const NativeFunctionImplementation& axismode_from_value_line_29_43c38e4a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.PivotControls",
        "ghostrigger::tools::workflow::pivotcontrols::core::scene::axis_mode",
        "src/core/scene/axis_mode.py",
        "AxisMode.from_value",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.PivotControls","namespace":"ghostrigger::tools::workflow::pivotcontrols::core::scene::axis_mode","python_file":"src/core/scene/axis_mode.py","qualname":"AxisMode.from_value","name":"from_value","callable_type":"class_methods","line":29,"end_line":36,"signature":{"args":["cls","value"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        axismode_from_value_line_29_43c38e4a_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::workflow::pivotcontrols
