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

const char* src_kotormcp_tools_debug_skinning_debugsession_load_model_depth_line_288_7527285a_descriptor_json();
const char* src_kotormcp_tools_debug_skinning_debugsession_get_bone_hierarchy_build_tree_line_606_3daacf2b_descriptor_json();
const char* src_kotormcp_tools_ghostrigger_tools_close_quat_close_line_104_b36abb8a_descriptor_json();
const char* src_kotormcp_tools_ghostrigger_tools_compare_model_pipelines_add_line_261_5b32c5d1_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
