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

const char* src_mesh_tools_mesh_edit_types_meshselectionmode_label_line_27_440b6e12_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_meshtools
