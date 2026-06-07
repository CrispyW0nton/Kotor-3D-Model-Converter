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

const char* src_mesh_tools_mesh_edit_types_meshoperationresult_ok_line_42_faf3927d_descriptor_json();
const char* src_mesh_tools_mesh_edit_types_meshoperationresult_fail_line_61_15657c24_descriptor_json();
const char* src_mesh_tools_mesh_topology_meshtopology_build_from_mesh_line_64_8c7ee68b_descriptor_json();
const char* src_mesh_tools_mesh_topology_meshtopology_rebuild_after_edit_line_72_26c2a3ab_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_meshtools
