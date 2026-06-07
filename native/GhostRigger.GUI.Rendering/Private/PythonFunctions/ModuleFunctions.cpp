#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::gui::rendering {

const NativeFunctionImplementation& getattr_line_18_624b26a0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.GUI.Rendering",
        "ghostrigger::gui::rendering::qt_gpu_renderer",
        "src/gui/rendering/qt_gpu_renderer.py",
        "__getattr__",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.GUI.Rendering","namespace":"ghostrigger::gui::rendering::qt_gpu_renderer","python_file":"src/gui/rendering/qt_gpu_renderer.py","qualname":"__getattr__","name":"__getattr__","callable_type":"module_functions","line":18,"end_line":25,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& dir_line_28_5ac68b36_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.GUI.Rendering",
        "ghostrigger::gui::rendering::qt_gpu_renderer",
        "src/gui/rendering/qt_gpu_renderer.py",
        "__dir__",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.GUI.Rendering","namespace":"ghostrigger::gui::rendering::qt_gpu_renderer","python_file":"src/gui/rendering/qt_gpu_renderer.py","qualname":"__dir__","name":"__dir__","callable_type":"module_functions","line":28,"end_line":29,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        getattr_line_18_624b26a0_native(),
        dir_line_28_5ac68b36_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::gui::rendering
