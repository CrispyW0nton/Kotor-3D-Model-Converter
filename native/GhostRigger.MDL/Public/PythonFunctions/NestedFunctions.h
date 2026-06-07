#pragma once

#include <cstddef>

namespace ghostrigger::mdl {

#ifndef GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& ghostriggertrimeshheader_read_read_i32_as_u32_line_104_2570ace6_native();
const NativeFunctionImplementation& ghostriggernode_sanitize_light_header_trim_line_326_465d4bb7_native();
const NativeFunctionImplementation& mdlbinarywriter_build_collect_line_276_e22adbf6_native();
const NativeFunctionImplementation& mdlbinarywriter_animation_nodes_with_hierarchy_clone_stub_node_line_1227_cdeae576_native();
const NativeFunctionImplementation& mdlbinarywriter_animation_nodes_with_hierarchy_visit_line_1269_b7de480b_native();
const NativeFunctionImplementation& mdlbinarywriter_prepare_animation_only_state_collect_line_370_edba9dee_native();
const NativeFunctionImplementation& mdlbinarywriter_write_collect_line_472_853941a9_native();
const NativeFunctionImplementation& mdlbinarywriter_write_node_tree_dfs_line_774_bc015d3d_native();
const NativeFunctionImplementation& mdlbinarywriter_animation_nodes_with_hierarchy_clone_stub_node_line_1620_1319cce1_native();
const NativeFunctionImplementation& mdlbinarywriter_animation_nodes_with_hierarchy_visit_line_1664_6b486ffb_native();
const NativeFunctionImplementation& mdlbinarywriter_write_anim_node_tree_write_depth_first_line_1824_fbbbefed_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::mdl
