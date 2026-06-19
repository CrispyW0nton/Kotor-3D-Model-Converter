#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::tools::pivotcontrols {

const NativeFunctionImplementation& transformcontroller_tuple_attr_line_77_8f25bbb8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools.PivotControls",
        "ghostrigger::core::tools::pivotcontrols::core::gizmo::transform_controller",
        "src/core/gizmo/transform_controller.py",
        "TransformController._tuple_attr",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools.PivotControls","namespace":"ghostrigger::core::tools::pivotcontrols::core::gizmo::transform_controller","python_file":"src/core/gizmo/transform_controller.py","qualname":"TransformController._tuple_attr","name":"_tuple_attr","callable_type":"static_methods","line":77,"end_line":84,"signature":{"args":["obj","name","fallback","count"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        transformcontroller_tuple_attr_line_77_8f25bbb8_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::tools::pivotcontrols
