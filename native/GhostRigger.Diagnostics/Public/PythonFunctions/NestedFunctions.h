#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_diagnostics {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_diagnostics_diagnostics_run_model_diagnostics_emit_line_567_9da1a4d8_descriptor_json();
const char* src_core_diagnostics_module_reference_safety_available_index_add_line_165_1e892e06_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_diagnostics
