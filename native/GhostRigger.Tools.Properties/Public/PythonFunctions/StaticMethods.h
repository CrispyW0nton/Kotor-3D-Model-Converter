#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_properties {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_panels_module_editor_module_editor_properties_moduleeditorpropertiespanel_set_vector_line_85_4910d35b_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_properties
