#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_moderngl {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_rendering_moderngl_renderer_impl_gpurenderer_is_gpu_line_2716_996d44b7_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_moderngl
