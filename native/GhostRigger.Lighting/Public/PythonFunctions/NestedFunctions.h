#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_lighting {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_lighting_light_manager_lightmanager_make_light_node_all_nodes_with_generated_line_186_39c41903_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_lighting
