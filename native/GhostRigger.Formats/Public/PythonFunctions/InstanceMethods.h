#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_formats {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_formats_gff_reader_gffreader_init_line_72_dfce678b_descriptor_json();
const char* src_formats_gff_reader_gffreader_parse_line_78_be205ebe_descriptor_json();
const char* src_formats_gff_reader_gffreader_read_bytes_line_144_ff209d8d_descriptor_json();
const char* src_formats_gff_reader_gffreader_read_labels_line_149_ff8fb539_descriptor_json();
const char* src_formats_gff_reader_gffreader_resolve_field_line_157_a03cdab8_descriptor_json();
const char* src_formats_gff_reader_gffreader_decode_field_line_177_c72b6413_descriptor_json();
const char* src_formats_gff_types_resref_post_init_line_69_9f194fb8_descriptor_json();
const char* src_formats_gff_types_resref_str_line_73_bbfbb826_descriptor_json();
const char* src_formats_gff_types_resref_repr_line_76_5b7f3968_descriptor_json();
const char* src_formats_gff_types_resref_eq_line_79_e334f978_descriptor_json();
const char* src_formats_gff_types_resref_hash_line_86_5633a8af_descriptor_json();
const char* src_formats_gff_types_locstring_get_text_line_108_8ae306d5_descriptor_json();
const char* src_formats_gff_types_locstring_set_text_line_112_f1c0b094_descriptor_json();
const char* src_formats_gff_types_locstring_english_line_120_f21f6d63_descriptor_json();
const char* src_formats_gff_types_locstring_repr_line_123_7eb89e36_descriptor_json();
const char* src_formats_gff_types_gfffield_repr_line_145_9db077e3_descriptor_json();
const char* src_formats_gff_types_gffstruct_get_line_159_ecc1ed3f_descriptor_json();
const char* src_formats_gff_types_gffstruct_set_line_163_8310b516_descriptor_json();
const char* src_formats_gff_types_gffstruct_getitem_line_166_824d2507_descriptor_json();
const char* src_formats_gff_types_gffstruct_setitem_line_169_1f5ee4f9_descriptor_json();
const char* src_formats_gff_types_gffstruct_contains_line_175_def2e01d_descriptor_json();
const char* src_formats_gff_types_gffstruct_repr_line_178_b6d9e7ff_descriptor_json();
const char* src_formats_gff_types_gfffile_get_line_194_74808bbd_descriptor_json();
const char* src_formats_gff_types_gfffile_set_line_197_49740131_descriptor_json();
const char* src_formats_gff_types_gfffile_repr_line_200_bfb6c7e7_descriptor_json();
const char* src_formats_gff_writer_gffwriter_init_line_47_8242ea74_descriptor_json();
const char* src_formats_gff_writer_gffwriter_serialize_line_52_d944781b_descriptor_json();
const char* src_formats_gff_writer_gffwriter_encode_field_line_204_b42c6c8e_descriptor_json();
const char* src_formats_gff_writer_gffwriter_encode_locstring_line_287_075bcc3c_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_formats
