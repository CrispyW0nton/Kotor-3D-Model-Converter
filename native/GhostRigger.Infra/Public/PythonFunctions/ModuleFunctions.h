#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_infra {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_infra_mcp_autostart_maybe_autostart_kotormcp_line_17_3a73802a_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_infra
