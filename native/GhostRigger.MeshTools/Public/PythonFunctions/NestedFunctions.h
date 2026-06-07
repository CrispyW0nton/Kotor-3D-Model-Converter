#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_meshtools {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_mesh_tools_mesh_weld_cluster_vertices_find_line_60_b7051c5a_descriptor_json();
const char* src_mesh_tools_mesh_weld_cluster_vertices_union_line_66_9b38cc0d_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_meshtools
