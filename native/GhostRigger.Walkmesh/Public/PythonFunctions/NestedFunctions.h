#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_walkmesh {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_extract_geometry_add_vert_line_607_14e49cd1_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_walkmesh
