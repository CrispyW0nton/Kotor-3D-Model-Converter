#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::core::gui::gizmo {

const NativeFunctionImplementation& getattr_line_20_0dc9caf2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Gizmo",
        "ghostrigger::core::gui::gizmo::init",
        "src/gui/gizmo/__init__.py",
        "__getattr__",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Gizmo","namespace":"ghostrigger::core::gui::gizmo::init","python_file":"src/gui/gizmo/__init__.py","qualname":"__getattr__","name":"__getattr__","callable_type":"module_functions","line":20,"end_line":26,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& dir_line_29_ef1640f7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Gizmo",
        "ghostrigger::core::gui::gizmo::init",
        "src/gui/gizmo/__init__.py",
        "__dir__",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Gizmo","namespace":"ghostrigger::core::gui::gizmo::init","python_file":"src/gui/gizmo/__init__.py","qualname":"__dir__","name":"__dir__","callable_type":"module_functions","line":29,"end_line":30,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        getattr_line_20_0dc9caf2_native(),
        dir_line_29_ef1640f7_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::gui::gizmo
