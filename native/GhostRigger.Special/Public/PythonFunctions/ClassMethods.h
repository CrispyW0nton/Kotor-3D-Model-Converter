#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_special {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_special_lip_reader_lipshape_label_line_82_0c06e812_descriptor_json();
const char* src_core_special_lip_reader_lipshape_from_phoneme_line_98_4a5108b5_descriptor_json();
const char* src_core_special_lip_reader_lipfile_from_bytes_line_155_70542997_descriptor_json();
const char* src_core_special_lip_reader_lipfile_from_file_line_190_1a30d4ed_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_special
