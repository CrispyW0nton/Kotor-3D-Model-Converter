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

const char* src_core_rendering_skeleton_render_data_cached_world_position_resolver_world_transform_line_189_c0b42698_descriptor_json();
const char* src_core_rendering_skeleton_render_data_cached_world_position_resolver_world_position_line_217_44c528c3_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors
