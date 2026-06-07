#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_pygfx {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_rendering_pygfx_core_renderer_pygfxviewportrenderer_probe_availability_line_87_bda39575_descriptor_json();
const char* src_adapters_rendering_pygfx_core_scene_bridge_pygfxscenebridge_polyline_to_segments_line_524_5d05e78c_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_pygfx
