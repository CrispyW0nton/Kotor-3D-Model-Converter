#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_lighting {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_lighting_init_getattr_line_23_8dc4fe30_descriptor_json();
const char* src_gui_lighting_init_dir_line_32_48350e38_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_lighting
