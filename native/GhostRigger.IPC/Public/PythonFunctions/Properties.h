#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_ipc {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_ipc_server_ghostriggeripcserver_is_running_line_86_e9c58b6b_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_ipc
