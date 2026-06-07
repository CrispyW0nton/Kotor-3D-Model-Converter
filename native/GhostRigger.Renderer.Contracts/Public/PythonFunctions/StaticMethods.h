#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_contracts {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_rendering_renderer_settings_renderersettings_apply_defaults_line_152_cad434f7_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_contracts
