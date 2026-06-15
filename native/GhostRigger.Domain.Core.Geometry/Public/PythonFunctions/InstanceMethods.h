#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::geometry {

#ifndef GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GEOMETRY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& vertexskindata_normalize_line_655_adabe2a1_native();
const NativeFunctionImplementation& vertexskindata_to_packed_line_661_f2afdae3_native();
const NativeFunctionImplementation& modelnode_compute_bounds_line_906_b54f13bd_native();
const NativeFunctionImplementation& modelnode_world_position_line_920_3212a140_native();
const NativeFunctionImplementation& modelnode_bone_world_position_line_985_2e0a3ca1_native();
const NativeFunctionImplementation& modelnode_world_transform_line_1034_ff665d1c_native();
const NativeFunctionImplementation& modelnode_compute_tangents_line_1083_3ddc0c29_native();
const NativeFunctionImplementation& modelnode_compute_tangents_line_1179_9c622130_native();
const NativeFunctionImplementation& modelnode_clone_shallow_line_1276_eea38d74_native();
const NativeFunctionImplementation& supermodelchain_loaded_models_line_1357_c862f246_native();
const NativeFunctionImplementation& kotormodel_all_nodes_line_1427_dd483f08_native();
const NativeFunctionImplementation& kotormodel_mesh_nodes_line_1456_9a385185_native();
const NativeFunctionImplementation& kotormodel_bone_nodes_line_1459_92284c78_native();
const NativeFunctionImplementation& kotormodel_find_node_line_1471_a4f9dc4c_native();
const NativeFunctionImplementation& kotormodel_compute_all_tangents_line_1477_50105b62_native();
const NativeFunctionImplementation& kotormodel_compute_bounds_line_1502_03f3f4b2_native();
const NativeFunctionImplementation& kotormodel_render_bounds_line_1550_96e90d04_native();
const NativeFunctionImplementation& kotormodel_node_count_line_1690_5ba7ecd1_native();
const NativeFunctionImplementation& kotormodel_texture_list_line_1693_818b2b0c_native();
const NativeFunctionImplementation& kotormodel_compute_all_tangents_legacy_line_1702_065c0bf0_native();
const NativeFunctionImplementation& sceneslot_post_construct_line_1792_5550caed_native();
const NativeFunctionImplementation& characterscene_post_construct_line_1853_0ced5b3c_native();
const NativeFunctionImplementation& characterscene_recompute_mode_line_1864_a56b9830_native();
const NativeFunctionImplementation& characterscene_set_mode_line_1924_c8431a53_native();
const NativeFunctionImplementation& characterscene_unlock_mode_line_1940_f348b0d5_native();
const NativeFunctionImplementation& characterscene_assign_line_1947_e1004bec_native();
const NativeFunctionImplementation& characterscene_clear_slot_line_1979_a0caa73f_native();
const NativeFunctionImplementation& characterscene_get_line_1986_f188529f_native();
const NativeFunctionImplementation& characterscene_get_model_line_1990_804798c8_native();
const NativeFunctionImplementation& characterscene_mark_clean_line_2019_4fa7fd2a_native();
const NativeFunctionImplementation& characterscene_asset_id_for_line_2025_7db1e454_native();
const NativeFunctionImplementation& characterscene_summary_line_2030_6cff1d6c_native();
const NativeFunctionImplementation& characterscene_to_dict_line_2083_38492785_native();
const NativeFunctionImplementation& characterscene_to_json_line_2308_675ed452_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::geometry
