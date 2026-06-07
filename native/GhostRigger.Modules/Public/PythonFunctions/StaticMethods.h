#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_modules {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_modules_module_editor_controller_moduleeditorcontroller_blueprint_type_for_library_asset_line_165_6428786f_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_modules
