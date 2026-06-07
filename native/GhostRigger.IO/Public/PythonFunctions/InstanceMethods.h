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

const char* src_io_fbx_fbx_scene_adapter_fbximportsummary_log_line_line_23_d3f43f45_descriptor_json();
const char* src_io_fbx_fbx_scene_adapter_fbxexportsummary_log_line_line_39_848f749e_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_io
