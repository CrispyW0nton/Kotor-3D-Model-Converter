#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_runtime {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_qt_core_make_package_line_293_8ece9a00_descriptor_json();
const char* src_core_qt_core_register_alias_line_300_993b5427_descriptor_json();
const char* src_core_qt_core_register_group_line_310_731fa624_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_runtime
