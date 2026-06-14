#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::spritematerials {

#ifndef GHOSTRIGGER_TOOLS_SPRITEMATERIALS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_SPRITEMATERIALS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_SPRITEMATERIALS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& is_tpc_data_line_21_56991bd7_native();
const NativeFunctionImplementation& is_tpc_file_line_103_58c8812d_native();
const NativeFunctionImplementation& decompress_dxt1_bytes_line_113_56e741e0_native();
const NativeFunctionImplementation& decompress_dxt5_bytes_line_159_f508a425_native();
const NativeFunctionImplementation& ensure_bottom_up_line_199_d5a36106_native();
const NativeFunctionImplementation& load_tpc_bytes_line_257_03436037_native();
const NativeFunctionImplementation& extract_txi_from_tpc_line_345_370af0a0_native();
const NativeFunctionImplementation& load_tpc_bytes_legacy_line_369_59664c39_native();
const NativeFunctionImplementation& load_tpc_bytes_legacy_inner_line_398_1578225a_native();
const NativeFunctionImplementation& extract_txi_from_tpc_legacy_line_585_b7d431dc_native();
const NativeFunctionImplementation& normalize_line_45_c928b456_native();
const NativeFunctionImplementation& clean_tex_name_line_49_5185b106_native();
const NativeFunctionImplementation& lerp_line_58_ffc177cb_native();
const NativeFunctionImplementation& uwrap_global_line_61_e4284d38_native();
const NativeFunctionImplementation& edge_has_seam_global_line_68_d7b46ead_native();
const NativeFunctionImplementation& vflip_nontiled_line_75_3eb9b7bb_native();
const NativeFunctionImplementation& vflip_tiled_line_79_d5112866_native();
const NativeFunctionImplementation& is_tpc_data_line_85_5f5162ea_native();
const NativeFunctionImplementation& is_tpc_file_line_143_542723f6_native();
const NativeFunctionImplementation& decompress_dxt1_bytes_line_153_bea423c9_native();
const NativeFunctionImplementation& decompress_dxt5_bytes_line_189_48a9f687_native();
const NativeFunctionImplementation& load_tpc_bytes_line_228_89ab9f25_native();
const NativeFunctionImplementation& paste_textured_triangle_line_414_d4547733_native();
const NativeFunctionImplementation& parse_txi_string_line_19_90baf54b_native();
const NativeFunctionImplementation& extract_alpha_test_from_tpc_line_285_052c2d77_native();
const NativeFunctionImplementation& apply_txi_to_node_line_319_913a6ad9_native();
const NativeFunctionImplementation& compute_flipbook_uv_line_413_476971ae_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::spritematerials
