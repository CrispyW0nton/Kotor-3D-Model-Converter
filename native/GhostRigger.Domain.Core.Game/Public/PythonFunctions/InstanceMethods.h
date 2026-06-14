#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::game {

#ifndef GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& tlkreader_construct_line_167_2f3cdaf4_native();
const NativeFunctionImplementation& tlkreader_load_line_172_76724e95_native();
const NativeFunctionImplementation& tlkreader_parse_line_183_18ef6c07_native();
const NativeFunctionImplementation& tlkreader_get_line_217_f3a16685_native();
const NativeFunctionImplementation& tlkreader_len_line_225_640e6bea_native();
const NativeFunctionImplementation& tlkreader_repr_line_230_f271490e_native();
const NativeFunctionImplementation& gffreader_parse_line_268_943754d3_native();
const NativeFunctionImplementation& gffreader_read_struct_line_300_eb335a17_native();
const NativeFunctionImplementation& gffreader_read_field_line_341_d4df73a7_native();
const NativeFunctionImplementation& bifindex_construct_line_96_e3f5caa3_native();
const NativeFunctionImplementation& bifindex_read_line_114_0d60c198_native();
const NativeFunctionImplementation& erfindex_construct_line_143_5d938732_native();
const NativeFunctionImplementation& erfindex_read_line_171_dc98b23d_native();
const NativeFunctionImplementation& erfindex_list_resrefs_line_184_2c017a44_native();
const NativeFunctionImplementation& kotorinstallation_construct_line_207_57ceb3a6_native();
const NativeFunctionImplementation& kotorinstallation_index_key_line_226_2f3fe143_native();
const NativeFunctionImplementation& kotorinstallation_find_case_insensitive_line_274_f943828e_native();
const NativeFunctionImplementation& kotorinstallation_index_texture_erfs_line_291_6286ce79_native();
const NativeFunctionImplementation& kotorinstallation_index_override_line_314_6fc556f2_native();
const NativeFunctionImplementation& kotorinstallation_get_line_339_70b9faa4_native();
const NativeFunctionImplementation& kotorinstallation_get_mdl_line_372_3f15db89_native();
const NativeFunctionImplementation& kotorinstallation_get_mdx_line_375_65bb5366_native();
const NativeFunctionImplementation& kotorinstallation_get_texture_line_378_fc7172f8_native();
const NativeFunctionImplementation& kotorinstallation_get_txi_line_385_6e34ec67_native();
const NativeFunctionImplementation& kotorinstallation_list_resrefs_line_397_53b3eb1b_native();
const NativeFunctionImplementation& kotorinstallation_list_models_line_414_0bcbeab2_native();
const NativeFunctionImplementation& kotorinstallation_list_textures_line_417_bb7d581d_native();
const NativeFunctionImplementation& kotorinstallation_has_resource_line_420_bd25a366_native();
const NativeFunctionImplementation& kotorinstallation_load_model_line_432_191d1877_native();
const NativeFunctionImplementation& kotorinstallation_load_texture_image_line_449_8915f60b_native();
const NativeFunctionImplementation& mdxdataoffsetzero_new_line_61_4137355e_native();
const NativeFunctionImplementation& mdxdataoffsetzero_eq_line_64_f90d326b_native();
const NativeFunctionImplementation& mdxdataoffsetzero_hash_line_69_6dfe63d9_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::game
