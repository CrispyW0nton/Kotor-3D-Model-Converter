#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_adapters_qtipc {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_qt_ipc_threading_marshal_to_gui_thread_line_9_545a70bd_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_adapters_qtipc
