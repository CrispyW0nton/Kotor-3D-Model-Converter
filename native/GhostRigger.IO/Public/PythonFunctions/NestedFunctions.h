#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_io {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_io_fbx_fbx_scene_adapter_fbx_mesh_to_gr_mesh_add_poly_vertex_line_172_858003db_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_io
