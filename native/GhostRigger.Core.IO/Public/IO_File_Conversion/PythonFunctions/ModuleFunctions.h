#pragma once

#include <cstddef>

namespace ghostrigger::core::converters {

#ifndef GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_CONVERTERS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& import_fbx_mesh_with_blender_line_36_72cb2d44_native();
const NativeFunctionImplementation& model_from_blender_fbx_mesh_payload_line_106_2efe69b6_native();
const NativeFunctionImplementation& attach_imported_armature_guides_line_196_944dc899_native();
const NativeFunctionImplementation& optional_triple_line_302_ac85f0c9_native();
const NativeFunctionImplementation& output_json_path_line_314_7126c45c_native();
const NativeFunctionImplementation& triple_line_324_268acf83_native();
const NativeFunctionImplementation& pair_line_329_7bfb8a8e_native();
const NativeFunctionImplementation& face_line_334_a80e1f65_native();
const NativeFunctionImplementation& skin_vertex_line_339_7e47defb_native();
const NativeFunctionImplementation& renderable_mesh_nodes_line_948_99f7f44a_native();
const NativeFunctionImplementation& export_rigging_data_line_978_bbde667e_native();
const NativeFunctionImplementation& tga_to_tpc_line_2649_0fa16c69_native();
const NativeFunctionImplementation& tpc_to_tga_line_2728_cb425a79_native();
const NativeFunctionImplementation& decompress_dxt1_line_2826_b5a4c5a2_native();
const NativeFunctionImplementation& decompress_dxt5_line_2860_4d4bc427_native();
const NativeFunctionImplementation& gen_mips_line_2892_b39293fc_native();
const NativeFunctionImplementation& gltf_round_trip_verify_line_3933_7335d549_native();
const NativeFunctionImplementation& normalize3_line_354_74c93553_native();
const NativeFunctionImplementation& dot3_line_360_9b483c5d_native();
const NativeFunctionImplementation& cross3_line_363_6ab633ea_native();
const NativeFunctionImplementation& lerp3_line_368_018e7d43_native();
const NativeFunctionImplementation& barycentric_uv_line_374_8e62e29e_native();
const NativeFunctionImplementation& compute_tangent_line_394_af510af5_native();
const NativeFunctionImplementation& world_to_tangent_line_412_48c8f8f4_native();
const NativeFunctionImplementation& ray_triangle_intersect_line_419_373cf1f5_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::converters
