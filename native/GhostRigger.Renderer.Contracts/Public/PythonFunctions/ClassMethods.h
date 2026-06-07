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

const char* src_core_rendering_renderer_capabilities_renderercapabilities_from_dict_line_104_185dfd96_descriptor_json();
const char* src_core_rendering_renderer_settings_renderersettings_from_settings_line_68_2bcc02b5_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_contracts
