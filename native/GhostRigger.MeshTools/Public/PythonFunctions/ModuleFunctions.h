#pragma once

#include <cstddef>

namespace ghostrigger::meshtools {

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

const NativeFunctionImplementation& attach_selected_meshes_line_10_282c2932_native();
const NativeFunctionImplementation& is_mesh_line_86_a952fc27_native();
const NativeFunctionImplementation& world_vertices_line_90_54e74ea7_native();
const NativeFunctionImplementation& extend_vertex_channel_line_101_6724dfba_native();
const NativeFunctionImplementation& compatible_channels_line_109_22108ab8_native();
const NativeFunctionImplementation& combined_name_line_116_4a578f66_native();
const NativeFunctionImplementation& cap_selected_borders_line_10_6a74d032_native();
const NativeFunctionImplementation& default_material_for_cap_line_49_b1a74bea_native();
const NativeFunctionImplementation& refresh_mesh_line_61_8b693d30_native();
const NativeFunctionImplementation& mesh_id_line_66_0f33d3c3_native();
const NativeFunctionImplementation& bridge_selected_line_10_a47a2001_native();
const NativeFunctionImplementation& strip_closing_vertex_line_66_79d80aad_native();
const NativeFunctionImplementation& connect_selected_line_10_0e1eb981_native();
const NativeFunctionImplementation& connect_vertices_line_19_ecbd1e9b_native();
const NativeFunctionImplementation& connect_edges_line_40_19ec004e_native();
const NativeFunctionImplementation& midpoint_vertex_line_61_303e08da_native();
const NativeFunctionImplementation& mesh_id_line_83_28c2e0ed_native();
const NativeFunctionImplementation& select_element_for_face_line_8_d155980b_native();
const NativeFunctionImplementation& snapshot_mesh_line_78_b7387527_native();
const NativeFunctionImplementation& restore_snapshot_line_85_845dec61_native();
const NativeFunctionImplementation& delete_selected_line_16_26a07979_native();
const NativeFunctionImplementation& remove_isolated_vertices_line_52_01d0d331_native();
const NativeFunctionImplementation& flip_normals_line_69_feb11d98_native();
const NativeFunctionImplementation& recalculate_normals_line_84_7a5932ab_native();
const NativeFunctionImplementation& detach_selection_line_90_fbaffdc2_native();
const NativeFunctionImplementation& selected_face_indices_line_121_5aeb8bf8_native();
const NativeFunctionImplementation& mesh_id_line_138_1770cbc9_native();
const NativeFunctionImplementation& remap_vertex_attributes_line_10_32df41d5_native();
const NativeFunctionImplementation& filter_face_attributes_line_42_de0b48af_native();
const NativeFunctionImplementation& append_face_attributes_line_52_2db65328_native();
const NativeFunctionImplementation& convert_selection_line_10_c761e266_native();
const NativeFunctionImplementation& loop_has_selected_edge_line_85_49f1deff_native();
const NativeFunctionImplementation& normalize_edge_line_13_80180e3b_native();
const NativeFunctionImplementation& vec_sub_line_20_e6d5b01d_native();
const NativeFunctionImplementation& cross_line_24_ddd174d9_native();
const NativeFunctionImplementation& length_line_32_9c936e17_native();
const NativeFunctionImplementation& normal_line_36_3a49f3b4_native();
const NativeFunctionImplementation& face_edges_line_272_c9079cd7_native();
const NativeFunctionImplementation& validate_mesh_line_9_6f28607f_native();
const NativeFunctionImplementation& weld_selected_vertices_line_14_124c1c61_native();
const NativeFunctionImplementation& target_weld_vertex_line_31_2877ab55_native();
const NativeFunctionImplementation& target_weld_edge_line_45_aef313df_native();
const NativeFunctionImplementation& cluster_vertices_line_57_392a6c07_native();
const NativeFunctionImplementation& collapse_groups_line_81_809ae7f0_native();
const NativeFunctionImplementation& compact_vertex_attributes_line_132_579b86ca_native();
const NativeFunctionImplementation& distance_line_139_1cbd57cc_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::meshtools
