#pragma once

#include <cstddef>

namespace ghostrigger::core::mdl {

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

const NativeFunctionImplementation& logical_reader_size_line_30_b056507b_native();
const NativeFunctionImplementation& array_count_within_reader_line_35_2d55f174_native();
const NativeFunctionImplementation& rstrip_line_25_4c27425d_native();
const NativeFunctionImplementation& bpad_line_37_1df7c2d8_native();
const NativeFunctionImplementation& ru32_line_40_93b9d9f7_native();
const NativeFunctionImplementation& rf32_line_41_ba7066cd_native();
const NativeFunctionImplementation& ru16_line_42_5b69032d_native();
const NativeFunctionImplementation& verify_emitter_ctrl_id_line_710_228551dd_native();
const NativeFunctionImplementation& ascii_type_to_flags_line_955_53e50f94_native();
const NativeFunctionImplementation& port_model_file_line_1415_2ae94d0f_native();
const NativeFunctionImplementation& iter_all_line_1457_d19e8ca8_native();
const NativeFunctionImplementation& read_mdl_safe_line_34_2eb8f3a9_native();
const NativeFunctionImplementation& is_mdl_aabb_seek_oserror_line_73_806c01b4_native();
const NativeFunctionImplementation& mesh_fp_pair_line_183_29ef6c4e_native();
const NativeFunctionImplementation& wu32_line_210_014bf470_native();
const NativeFunctionImplementation& wi32_line_213_982f762e_native();
const NativeFunctionImplementation& wu16_line_216_1d7ff7b2_native();
const NativeFunctionImplementation& wf32_line_219_937948cb_native();
const NativeFunctionImplementation& wstr_line_224_1aa49ba8_native();
const NativeFunctionImplementation& align4_line_229_befe9b85_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::mdl
