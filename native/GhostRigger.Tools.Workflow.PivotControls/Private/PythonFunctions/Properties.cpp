#include "PythonFunctions/Properties.h"

namespace ghostrigger::tools::workflow::pivotcontrols {

const NativeFunctionImplementation& axismode_label_line_25_7f940ea5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.PivotControls",
        "ghostrigger::tools::workflow::pivotcontrols::core::scene::axis_mode",
        "src/core/scene/axis_mode.py",
        "AxisMode.label",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.PivotControls","namespace":"ghostrigger::tools::workflow::pivotcontrols::core::scene::axis_mode","python_file":"src/core/scene/axis_mode.py","qualname":"AxisMode.label","name":"label","callable_type":"properties","line":25,"end_line":26,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        axismode_label_line_25_7f940ea5_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::workflow::pivotcontrols
