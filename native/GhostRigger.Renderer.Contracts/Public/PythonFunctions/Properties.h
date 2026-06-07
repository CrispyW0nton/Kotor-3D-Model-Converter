#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_contracts {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_rendering_renderer_factory_fallbackviewportrenderer_name_line_127_fde2575f_descriptor_json();
const char* src_adapters_rendering_renderer_factory_fallbackviewportrenderer_backend_id_line_132_2bc3f975_descriptor_json();
const char* src_adapters_rendering_renderer_factory_fallbackviewportrenderer_active_renderer_line_196_3eb56d6b_descriptor_json();
const char* src_adapters_rendering_renderer_factory_fallbackviewportrenderer_active_backend_line_200_710bb50c_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_contracts
