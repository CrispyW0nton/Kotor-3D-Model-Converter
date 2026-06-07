#pragma once

#include <cstddef>

namespace ghostrigger::skeleton {

#ifndef GHOSTRIGGER_SKELETON_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SKELETON_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_SKELETON_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& bind_imported_meshes_to_skeleton_line_42_8c21e061_native();
const NativeFunctionImplementation& candidate_bones_line_205_45148d86_native();
const NativeFunctionImplementation& is_deform_candidate_line_220_5bb32fff_native();
const NativeFunctionImplementation& imported_mesh_payloads_line_239_7d29b1b1_native();
const NativeFunctionImplementation& bone_slots_line_252_dd3f0e52_native();
const NativeFunctionImplementation& weights_for_vertex_line_266_3b24781c_native();
const NativeFunctionImplementation& weights_for_vertex_with_donor_line_289_465d2469_native();
const NativeFunctionImplementation& build_donor_vertex_index_line_307_7977e6fa_native();
const NativeFunctionImplementation& map_donor_influences_to_slots_line_350_61c60ca2_native();
const NativeFunctionImplementation& nearest_donor_vertex_line_379_543fc617_native();
const NativeFunctionImplementation& normalize_influences_line_393_f4394482_native();
const NativeFunctionImplementation& compact_skin_bone_map_to_used_influences_line_419_b8b64074_native();
const NativeFunctionImplementation& used_influence_indices_line_487_a4a04898_native();
const NativeFunctionImplementation& filter_parallel_list_line_504_ccc05097_native();
const NativeFunctionImplementation& mesh_binding_report_line_516_49dd1ef2_native();
const NativeFunctionImplementation& transform_point_line_574_29b0bdb7_native();
const NativeFunctionImplementation& quat_rotate_vec_line_587_b17df509_native();
const NativeFunctionImplementation& make_skin_node_line_606_36ea11ae_native();
const NativeFunctionImplementation& child_positions_line_613_f85807df_native();
const NativeFunctionImplementation& node_world_line_628_75cafaa7_native();
const NativeFunctionImplementation& has_vertices_line_643_c4d17845_native();
const NativeFunctionImplementation& is_non_deform_hook_line_647_91e659ca_native();
const NativeFunctionImplementation& vec3_line_652_05721302_native();
const NativeFunctionImplementation& quat_line_657_7e1d187a_native();
const NativeFunctionImplementation& distance_line_664_46b727fc_native();
const NativeFunctionImplementation& distance_point_segment_line_668_6562c54f_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::skeleton
