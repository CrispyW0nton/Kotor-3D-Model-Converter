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

const char* src_formats_gff_reader_read_gff_line_271_ba45cf01_descriptor_json();
const char* src_formats_gff_writer_write_gff_line_306_9e3facfa_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_formats
