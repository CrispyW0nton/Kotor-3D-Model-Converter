#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_io {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_io_fbx_fbx_sdk_loader_fbxsdkmodules_available_line_22_df5f76b9_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_io
