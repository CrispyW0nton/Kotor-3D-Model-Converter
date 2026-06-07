#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_adapters_files {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_files_local_file_writer_localfilewriter_write_bytes_line_15_ad2c205d_descriptor_json();
const char* src_adapters_files_local_file_writer_localfilewriter_write_text_line_20_ec441b06_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_adapters_files
