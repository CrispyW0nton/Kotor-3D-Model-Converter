#pragma once

#include <cstddef>

namespace ghostrigger::core::meshtools {

#ifndef GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& meshvalidationreport_finalize_line_83_c99f7a66_native();
const NativeFunctionImplementation& meshhistory_snapshot_line_48_d6274781_native();
const NativeFunctionImplementation& meshhistory_record_line_51_351c6448_native();
const NativeFunctionImplementation& meshhistory_undo_line_59_b74df69f_native();
const NativeFunctionImplementation& meshhistory_redo_line_68_ff39d3ad_native();
const NativeFunctionImplementation& meshselectionstate_clear_subobject_selection_line_24_8a10cd0c_native();
const NativeFunctionImplementation& meshselectionstate_set_mode_line_32_278d09e2_native();
const NativeFunctionImplementation& meshselectionstate_set_edges_line_37_c08aaf4a_native();
const NativeFunctionImplementation& meshselectionstate_counts_line_40_7c95153d_native();
const NativeFunctionImplementation& meshtopology_build_line_75_e822ad39_native();
const NativeFunctionImplementation& meshtopology_build_face_adjacency_line_121_7b560c9d_native();
const NativeFunctionImplementation& meshtopology_build_border_loops_line_128_1087851e_native();
const NativeFunctionImplementation& meshtopology_build_connected_elements_line_155_3ecc8f6d_native();
const NativeFunctionImplementation& meshtopology_build_vertex_normals_line_172_64dce9e4_native();
const NativeFunctionImplementation& meshtopology_get_edges_line_187_d800dee9_native();
const NativeFunctionImplementation& meshtopology_get_border_edges_line_190_ba421b9e_native();
const NativeFunctionImplementation& meshtopology_get_border_loops_line_193_a0637b95_native();
const NativeFunctionImplementation& meshtopology_get_connected_elements_line_196_783e3810_native();
const NativeFunctionImplementation& meshtopology_get_faces_for_edge_line_199_138099a8_native();
const NativeFunctionImplementation& meshtopology_get_edges_for_face_line_202_349b2e7f_native();
const NativeFunctionImplementation& meshtopology_get_faces_for_vertex_line_208_87320bbf_native();
const NativeFunctionImplementation& meshtopology_border_index_for_edge_line_211_84d28637_native();
const NativeFunctionImplementation& meshtopology_find_edge_loop_line_221_0e9d42e9_native();
const NativeFunctionImplementation& meshtopology_find_edge_ring_line_234_b1276bf9_native();
const NativeFunctionImplementation& meshtopology_validate_manifold_state_line_246_fe75a94e_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::meshtools
