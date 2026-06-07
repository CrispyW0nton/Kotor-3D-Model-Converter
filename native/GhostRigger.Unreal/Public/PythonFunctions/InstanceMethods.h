#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_unreal {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_unreal_quinn_fbxnode_child_line_58_e1028af9_descriptor_json();
const char* src_unreal_quinn_fbxnode_children_named_line_64_07b0592d_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_unreal
