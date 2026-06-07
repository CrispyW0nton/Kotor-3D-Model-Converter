#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_kotormcp {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_kotormcp_server_fallbackhttpserver_handle_line_87_adab15d2_descriptor_json();
const char* src_kotormcp_server_fallbackhttpserver_serve_line_162_44154bbb_descriptor_json();

const PythonFunctionDescriptorEntry* asyncinstancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
