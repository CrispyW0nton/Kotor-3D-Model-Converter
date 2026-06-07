#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_kotormcp {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_kotormcp_adapters_filesystemmodellocator_load_mdx_line_401_1325659a_descriptor_json();
const char* src_kotormcp_adapters_modelanalyzer_all_nodes_line_571_84d72b05_descriptor_json();
const char* src_kotormcp_adapters_modelanalyzer_mesh_nodes_line_579_15aa35bb_descriptor_json();
const char* src_kotormcp_adapters_modelanalyzer_bone_nodes_line_604_bf59a565_descriptor_json();
const char* src_kotormcp_adapters_modelanalyzer_bbox_line_611_69879d13_descriptor_json();
const char* src_kotormcp_adapters_modelanalyzer_node_count_line_617_de9db12b_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
