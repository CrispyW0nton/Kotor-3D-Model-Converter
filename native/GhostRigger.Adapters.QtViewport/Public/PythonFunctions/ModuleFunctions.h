#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_adapters_qtviewport {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_qt_viewport_frame_renderer_create_viewport_frame_renderer_line_6_3db885a3_descriptor_json();
const char* src_adapters_qt_viewport_frame_renderer_create_validation_frame_renderer_line_13_70d85031_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_adapters_qtviewport
