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

const char* src_unreal_animation_retargeting_world_positions_by_key_visit_line_343_1fe69925_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_unreal
