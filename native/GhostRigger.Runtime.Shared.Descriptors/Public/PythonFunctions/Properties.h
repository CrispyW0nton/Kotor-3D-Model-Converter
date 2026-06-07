#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_scene_scene_object_pivotdata_position_line_54_fa472186_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_rotation_line_62_8f4a7cea_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors
