#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_twodabrowser {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_game_game_library_ext_gffreader_from_bytes_line_256_55910253_descriptor_json();
const char* src_core_templates_twoda_twoda_from_bytes_line_88_45af8178_descriptor_json();
const char* src_core_templates_twoda_twoda_from_file_line_103_aca436e4_descriptor_json();
const char* src_core_templates_twoda_twoda_parse_binary_line_114_bc648710_descriptor_json();
const char* src_core_templates_twoda_twoda_parse_ascii_line_200_d1371498_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_twodabrowser
