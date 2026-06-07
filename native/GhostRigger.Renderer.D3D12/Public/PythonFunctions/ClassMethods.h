#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_d3d12 {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_rendering_hardware_info_hardwarediagnostics_from_dict_line_56_a66bccdf_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_d3d12
