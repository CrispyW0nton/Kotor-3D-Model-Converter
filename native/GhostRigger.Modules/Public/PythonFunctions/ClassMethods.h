#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_modules {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_modules_module_format_lytlayout_from_text_line_75_b9b667dc_descriptor_json();
const char* src_core_modules_module_format_lytlayout_from_file_line_144_17b82126_descriptor_json();
const char* src_core_modules_module_format_visdata_from_text_line_182_25411b79_descriptor_json();
const char* src_core_modules_module_format_visdata_from_file_line_199_e4a72a20_descriptor_json();
const char* src_core_modules_module_format_aredata_from_bytes_line_249_49ea9dec_descriptor_json();
const char* src_core_modules_module_format_gitdata_from_bytes_line_353_69675c0d_descriptor_json();
const char* src_core_modules_module_format_ifodata_from_bytes_line_467_8b750a00_descriptor_json();
const char* src_core_modules_module_format_wokdata_from_bytes_line_555_79d73e9e_descriptor_json();
const char* src_core_modules_module_format_wokdata_from_pykotor_bwm_line_573_0083a2f7_descriptor_json();
const char* src_core_modules_module_format_wokdata_from_file_line_618_88ca04bf_descriptor_json();
const char* src_core_modules_module_format_kotormodule_from_directory_line_939_586f7036_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_modules
