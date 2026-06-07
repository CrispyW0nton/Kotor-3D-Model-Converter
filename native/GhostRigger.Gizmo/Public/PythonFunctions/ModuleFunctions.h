#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gizmo {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_gizmo_gizmo_draw_data_rgba255_to_float_line_38_22b0952d_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gizmo
