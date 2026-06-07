#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_sequence {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_sequence_sequence_manager_sequencemanager_safe_filename_line_174_6e8e07fc_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_sequence
