#pragma once

#include <cstddef>

namespace ghostrigger::walkmesh {

#ifndef GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& import_module_format_line_128_b17b2aa2_native();
const NativeFunctionImplementation& import_walkmesh_renderer_line_137_88470d36_native();
const NativeFunctionImplementation& module_from_input_line_147_c2b5ea5e_native();
const NativeFunctionImplementation& looks_like_wok_line_153_ea56805e_native();
const NativeFunctionImplementation& room_woks_line_157_3c189e0c_native();
const NativeFunctionImplementation& select_wok_line_165_95814c82_native();
const NativeFunctionImplementation& surface_names_line_187_0e0b3e30_native();
const NativeFunctionImplementation& walkable_ids_line_192_de93cc15_native();
const NativeFunctionImplementation& surface_name_line_197_62f14ef3_native();
const NativeFunctionImplementation& surface_color_line_202_576794ea_native();
const NativeFunctionImplementation& is_walkable_line_209_d58bfb9c_native();
const NativeFunctionImplementation& face_indices_line_213_deb3c831_native();
const NativeFunctionImplementation& face_adjacency_line_217_7c19b1ff_native();
const NativeFunctionImplementation& centroid_line_221_ee9ca26c_native();
const NativeFunctionImplementation& face_info_line_234_0b837fd0_native();
const NativeFunctionImplementation& surface_distribution_line_252_8f9f4efb_native();
const NativeFunctionImplementation& walkable_face_count_line_262_89163905_native();
const NativeFunctionImplementation& non_walk_face_count_line_268_99b04b19_native();
const NativeFunctionImplementation& boundary_edges_line_274_3d7fa03b_native();
const NativeFunctionImplementation& walkmesh_surface_palette_line_280_4a8498ac_native();
const NativeFunctionImplementation& build_walkmesh_workbench_line_294_c66ae8cf_native();
const NativeFunctionImplementation& select_walkmesh_face_line_331_12dab30c_native();
const NativeFunctionImplementation& set_walkmesh_face_surface_line_380_c294b580_native();
const NativeFunctionImplementation& paint_walkmesh_point_line_449_e2aaa4bf_native();
const NativeFunctionImplementation& validate_walkmesh_line_470_a514510b_native();
const NativeFunctionImplementation& roundtrip_walkmesh_line_584_8753b6a5_native();
const NativeFunctionImplementation& surface_color_line_117_64d9d09b_native();
const NativeFunctionImplementation& surface_name_line_122_416678cb_native();
const NativeFunctionImplementation& build_draw_list_line_457_d887c5f1_native();
const NativeFunctionImplementation& get_walkmesh_fbx_material_line_867_0fb07cd7_native();
const NativeFunctionImplementation& walkmesh_to_fbx_materials_line_887_e5348752_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::walkmesh
