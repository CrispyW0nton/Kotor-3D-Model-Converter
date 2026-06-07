#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_tools_camera {

const char* src_adapters_qt_viewport_camera_gizmo_renderer_cameragizmorenderer_hex_to_rgba_line_18_cf0993c0_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.Camera","python_module":"src.adapters.qt_viewport.camera_gizmo_renderer","python_file":"src/adapters/qt_viewport/camera_gizmo_renderer.py","qualname":"CameraGizmoRenderer._hex_to_rgba","name":"_hex_to_rgba","kind":"static_methods","line":18,"end_line":29,"signature":{"args":["value","fallback","alpha"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_adapters_qt_viewport_camera_gizmo_renderer_cameragizmorenderer_blend_line_32_f09bef2b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Tools.Camera","python_module":"src.adapters.qt_viewport.camera_gizmo_renderer","python_file":"src/adapters/qt_viewport/camera_gizmo_renderer.py","qualname":"CameraGizmoRenderer._blend","name":"_blend","kind":"static_methods","line":32,"end_line":34,"signature":{"args":["a","b","t"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/adapters/qt_viewport/camera_gizmo_renderer.py", "CameraGizmoRenderer._hex_to_rgba", "static_methods", &src_adapters_qt_viewport_camera_gizmo_renderer_cameragizmorenderer_hex_to_rgba_line_18_cf0993c0_descriptor_json},
        {"src/adapters/qt_viewport/camera_gizmo_renderer.py", "CameraGizmoRenderer._blend", "static_methods", &src_adapters_qt_viewport_camera_gizmo_renderer_cameragizmorenderer_blend_line_32_f09bef2b_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_tools_camera
