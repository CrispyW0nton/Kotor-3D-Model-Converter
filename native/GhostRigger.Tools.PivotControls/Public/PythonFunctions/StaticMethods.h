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

const char* src_core_gizmo_transform_controller_transformcontroller_tuple_attr_line_77_8f25bbb8_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_pivotcontrols
