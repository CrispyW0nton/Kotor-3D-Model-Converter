#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_animationretargeting {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_animation_retargeting_retargeter_world_positions_by_key_visit_line_201_388300ca_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_animationretargeting
