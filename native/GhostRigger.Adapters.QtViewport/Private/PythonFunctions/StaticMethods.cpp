#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::adapters::qtviewport {

const NativeFunctionImplementation& cameragizmorenderer_hex_to_rgba_line_18_cf0993c0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.QtViewport",
        "ghostrigger::adapters::qtviewport::qt_viewport::camera_gizmo_renderer",
        "src/adapters/qt_viewport/camera_gizmo_renderer.py",
        "CameraGizmoRenderer._hex_to_rgba",
        "static_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.QtViewport","namespace":"ghostrigger::adapters::qtviewport::qt_viewport::camera_gizmo_renderer","python_file":"src/adapters/qt_viewport/camera_gizmo_renderer.py","qualname":"CameraGizmoRenderer._hex_to_rgba","name":"_hex_to_rgba","callable_type":"static_methods","line":18,"end_line":29,"signature":{"args":["value","fallback","alpha"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cameragizmorenderer_blend_line_32_f09bef2b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.QtViewport",
        "ghostrigger::adapters::qtviewport::qt_viewport::camera_gizmo_renderer",
        "src/adapters/qt_viewport/camera_gizmo_renderer.py",
        "CameraGizmoRenderer._blend",
        "static_methods",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.QtViewport","namespace":"ghostrigger::adapters::qtviewport::qt_viewport::camera_gizmo_renderer","python_file":"src/adapters/qt_viewport/camera_gizmo_renderer.py","qualname":"CameraGizmoRenderer._blend","name":"_blend","callable_type":"static_methods","line":32,"end_line":34,"signature":{"args":["a","b","t"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        cameragizmorenderer_hex_to_rgba_line_18_cf0993c0_native(),
        cameragizmorenderer_blend_line_32_f09bef2b_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::adapters::qtviewport

