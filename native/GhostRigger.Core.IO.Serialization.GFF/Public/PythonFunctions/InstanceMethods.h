#pragma once

#include <cstddef>

namespace ghostrigger::core::io::serialization::gff {

#ifndef GHOSTRIGGER_FORMATS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_FORMATS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_FORMATS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& gffreader_construct_line_72_dfce678b_native();
const NativeFunctionImplementation& gffreader_parse_line_78_be205ebe_native();
const NativeFunctionImplementation& gffreader_read_bytes_line_144_ff209d8d_native();
const NativeFunctionImplementation& gffreader_read_labels_line_149_ff8fb539_native();
const NativeFunctionImplementation& gffreader_resolve_field_line_157_a03cdab8_native();
const NativeFunctionImplementation& gffreader_decode_field_line_177_c72b6413_native();
const NativeFunctionImplementation& resref_post_construct_line_69_9f194fb8_native();
const NativeFunctionImplementation& resref_str_line_73_bbfbb826_native();
const NativeFunctionImplementation& resref_repr_line_76_5b7f3968_native();
const NativeFunctionImplementation& resref_eq_line_79_e334f978_native();
const NativeFunctionImplementation& resref_hash_line_86_5633a8af_native();
const NativeFunctionImplementation& locstring_get_text_line_108_8ae306d5_native();
const NativeFunctionImplementation& locstring_set_text_line_112_f1c0b094_native();
const NativeFunctionImplementation& locstring_english_line_120_f21f6d63_native();
const NativeFunctionImplementation& locstring_repr_line_123_7eb89e36_native();
const NativeFunctionImplementation& gfffield_repr_line_145_9db077e3_native();
const NativeFunctionImplementation& gffstruct_get_line_159_ecc1ed3f_native();
const NativeFunctionImplementation& gffstruct_set_line_163_8310b516_native();
const NativeFunctionImplementation& gffstruct_getitem_line_166_824d2507_native();
const NativeFunctionImplementation& gffstruct_setitem_line_169_1f5ee4f9_native();
const NativeFunctionImplementation& gffstruct_contains_line_175_def2e01d_native();
const NativeFunctionImplementation& gffstruct_repr_line_178_b6d9e7ff_native();
const NativeFunctionImplementation& gfffile_get_line_194_74808bbd_native();
const NativeFunctionImplementation& gfffile_set_line_197_49740131_native();
const NativeFunctionImplementation& gfffile_repr_line_200_bfb6c7e7_native();
const NativeFunctionImplementation& gffwriter_construct_line_47_8242ea74_native();
const NativeFunctionImplementation& gffwriter_serialize_line_52_d944781b_native();
const NativeFunctionImplementation& gffwriter_encode_field_line_204_b42c6c8e_native();
const NativeFunctionImplementation& gffwriter_encode_locstring_line_287_075bcc3c_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::io::serialization::gff
