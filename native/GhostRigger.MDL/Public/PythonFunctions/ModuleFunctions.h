#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_mdl {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_mdl_ghostrigger_mdl_reader_logical_reader_size_line_30_b056507b_descriptor_json();
const char* src_core_mdl_ghostrigger_mdl_reader_array_count_within_reader_line_35_2d55f174_descriptor_json();
const char* src_core_mdl_mdl_parser_rstrip_line_25_4c27425d_descriptor_json();
const char* src_core_mdl_mdl_parser_bpad_line_37_1df7c2d8_descriptor_json();
const char* src_core_mdl_mdl_parser_ru32_line_40_93b9d9f7_descriptor_json();
const char* src_core_mdl_mdl_parser_rf32_line_41_ba7066cd_descriptor_json();
const char* src_core_mdl_mdl_parser_ru16_line_42_5b69032d_descriptor_json();
const char* src_core_mdl_mdl_parser_verify_emitter_ctrl_id_line_710_228551dd_descriptor_json();
const char* src_core_mdl_mdl_parser_ascii_type_to_flags_line_955_53e50f94_descriptor_json();
const char* src_core_mdl_mdl_porter_port_model_file_line_1415_2ae94d0f_descriptor_json();
const char* src_core_mdl_mdl_porter_iter_all_line_1457_d19e8ca8_descriptor_json();
const char* src_core_mdl_mdl_reader_wrapper_read_mdl_safe_line_34_2eb8f3a9_descriptor_json();
const char* src_core_mdl_mdl_reader_wrapper_is_mdl_aabb_seek_oserror_line_73_806c01b4_descriptor_json();
const char* src_core_mdl_mdl_writer_mesh_fp_pair_line_183_29ef6c4e_descriptor_json();
const char* src_core_mdl_mdl_writer_wu32_line_210_014bf470_descriptor_json();
const char* src_core_mdl_mdl_writer_wi32_line_213_982f762e_descriptor_json();
const char* src_core_mdl_mdl_writer_wu16_line_216_1d7ff7b2_descriptor_json();
const char* src_core_mdl_mdl_writer_wf32_line_219_937948cb_descriptor_json();
const char* src_core_mdl_mdl_writer_wstr_line_224_1aa49ba8_descriptor_json();
const char* src_core_mdl_mdl_writer_align4_line_229_befe9b85_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_mdl
