#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_adapters_scripts {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_scripts_unavailable_compiler_unavailablescriptcompiler_compile_script_line_29_00747c15_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_adapters_scripts
