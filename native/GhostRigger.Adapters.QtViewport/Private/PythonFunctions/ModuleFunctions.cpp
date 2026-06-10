#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::adapters::qtviewport {

const NativeFunctionImplementation& create_viewport_frame_renderer_line_6_3db885a3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.QtViewport",
        "ghostrigger::adapters::qtviewport::qt_viewport::frame_renderer",
        "src/adapters/qt_viewport/frame_renderer.py",
        "create_viewport_frame_renderer",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.QtViewport","namespace":"ghostrigger::adapters::qtviewport::qt_viewport::frame_renderer","python_file":"src/adapters/qt_viewport/frame_renderer.py","qualname":"create_viewport_frame_renderer","name":"create_viewport_frame_renderer","callable_type":"module_functions","line":6,"end_line":10,"signature":{"args":["viewport"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& create_validation_frame_renderer_line_13_70d85031_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.QtViewport",
        "ghostrigger::adapters::qtviewport::qt_viewport::frame_renderer",
        "src/adapters/qt_viewport/frame_renderer.py",
        "create_validation_frame_renderer",
        "module_functions",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.QtViewport","namespace":"ghostrigger::adapters::qtviewport::qt_viewport::frame_renderer","python_file":"src/adapters/qt_viewport/frame_renderer.py","qualname":"create_validation_frame_renderer","name":"create_validation_frame_renderer","callable_type":"module_functions","line":13,"end_line":24,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        create_viewport_frame_renderer_line_6_3db885a3_native(),
        create_validation_frame_renderer_line_13_70d85031_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::adapters::qtviewport

