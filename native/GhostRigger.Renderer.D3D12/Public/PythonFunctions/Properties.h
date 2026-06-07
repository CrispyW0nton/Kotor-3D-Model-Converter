#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_d3d12 {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_rendering_gpu_scene_helpers_compositemodel_nodes_line_292_c770f0f1_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_d3d12
