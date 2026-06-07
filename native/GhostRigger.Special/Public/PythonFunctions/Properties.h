#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_special {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_special_unity_malak_smoke_unitybridgeclient_endpoint_line_34_0219d326_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_special
