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

const char* src_core_mdl_mdl_parser_mdlbinaryparser_from_files_line_74_5167f1ce_descriptor_json();
const char* src_core_mdl_mdl_parser_mdlbinaryparser_parse_files_line_85_cd15af6e_descriptor_json();
const char* src_core_mdl_mdl_writer_mdlbinarywriter_ensure_export_orientation_controller_line_1723_b0eb1123_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_mdl
