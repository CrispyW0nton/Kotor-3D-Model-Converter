#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::converters {

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

const NativeFunctionImplementation& objimporter_import_file_flush_line_87_1fb37067_native();
const NativeFunctionImplementation& objimporter_import_file_new_group_line_92_b002e1cc_native();
const NativeFunctionImplementation& objimporter_make_node_gi_line_155_23f6585c_native();
const NativeFunctionImplementation& fbxexporter_export_fbx_ascii_new_id_line_1491_3c5a6030_native();
const NativeFunctionImplementation& fbxexporter_export_fbx_ascii_quat_to_euler_deg_line_1843_dcb2a96b_native();
const NativeFunctionImplementation& fbxexporter_export_fbx_ascii_world_matrix_col_major_line_1865_622a4fbc_native();
const NativeFunctionImplementation& fbxexporter_export_fbx_ascii_qbone_matrix_col_major_line_2079_6bd3c6c9_native();
const NativeFunctionImplementation& fbxexporter_export_fbx_ascii_write_anim_curve_line_2312_fcf8ef5f_native();
const NativeFunctionImplementation& fbxexporter_export_fbx_ascii_write_grouped_curves_line_2347_ed965d64_native();
const NativeFunctionImplementation& fbxexporter_export_fbx_ascii_quat_mul_line_2421_b242b201_native();
const NativeFunctionImplementation& decompress_dxt1_e565_line_2839_e248a9b2_native();
const NativeFunctionImplementation& decompress_dxt5_e565_line_2874_54635024_native();
const NativeFunctionImplementation& gltfimporter_load_pygltflib_get_accessor_data_line_2955_abb66ade_native();
const NativeFunctionImplementation& gltfexporter_export_pygltflib_add_accessor_line_3295_6516bad0_native();
const NativeFunctionImplementation& gltfexporter_export_pygltflib_pack_v_line_3568_be1ebf70_native();
const NativeFunctionImplementation& gltfexporter_export_pygltflib_pack_v_line_3575_9b5c23be_native();
const NativeFunctionImplementation& gltfexporter_export_pygltflib_pack_v_line_3583_5193d6a4_native();
const NativeFunctionImplementation& gltfexporter_export_manual_add_bv_line_3649_4f6d1cce_native();
const NativeFunctionImplementation& gltfexporter_export_manual_add_acc_line_3659_4b98012c_native();
const NativeFunctionImplementation& gltfexporter_export_manual_pv_line_3794_1bc29691_native();
const NativeFunctionImplementation& gltfexporter_export_manual_pv_line_3797_dc62e16e_native();
const NativeFunctionImplementation& gltfexporter_export_manual_pv_line_3801_cc34bf13_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::converters
