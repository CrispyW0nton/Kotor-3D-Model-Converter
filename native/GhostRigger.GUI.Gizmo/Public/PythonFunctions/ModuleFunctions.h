#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_gizmo {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_gizmo_init_getattr_line_20_0dc9caf2_descriptor_json();
const char* src_gui_gizmo_init_dir_line_29_ef1640f7_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_gizmo
