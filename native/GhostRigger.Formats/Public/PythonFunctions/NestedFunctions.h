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

const char* src_formats_gff_writer_gffwriter_serialize_collect_line_59_1e5f42ee_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_formats
