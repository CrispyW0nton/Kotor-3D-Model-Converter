#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_scene_axis_mode_axismode_from_value_line_29_43c38e4a_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols
