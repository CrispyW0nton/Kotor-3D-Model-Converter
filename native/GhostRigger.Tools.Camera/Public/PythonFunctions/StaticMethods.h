#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_camera {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_qt_viewport_camera_gizmo_renderer_cameragizmorenderer_hex_to_rgba_line_18_cf0993c0_descriptor_json();
const char* src_adapters_qt_viewport_camera_gizmo_renderer_cameragizmorenderer_blend_line_32_f09bef2b_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_camera
