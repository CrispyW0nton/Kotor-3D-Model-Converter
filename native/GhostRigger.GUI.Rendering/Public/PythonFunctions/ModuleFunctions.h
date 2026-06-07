#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_rendering {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_rendering_qt_gpu_renderer_getattr_line_18_624b26a0_descriptor_json();
const char* src_gui_rendering_qt_gpu_renderer_dir_line_28_5ac68b36_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_rendering
