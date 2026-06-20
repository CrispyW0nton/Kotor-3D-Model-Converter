#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::core::gizmo {

const NativeFunctionImplementation& rgba255_to_float_line_38_22b0952d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Helpers",
        "ghostrigger::core::gizmo::core::gizmo::gizmo_draw_data",
        "src/core/gizmo/gizmo_draw_data.py",
        "rgba255_to_float",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Helpers","namespace":"ghostrigger::core::gizmo::core::gizmo::gizmo_draw_data","python_file":"src/core/gizmo/gizmo_draw_data.py","qualname":"rgba255_to_float","name":"rgba255_to_float","callable_type":"module_functions","line":38,"end_line":46,"signature":{"args":["color"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        rgba255_to_float_line_38_22b0952d_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::gizmo
