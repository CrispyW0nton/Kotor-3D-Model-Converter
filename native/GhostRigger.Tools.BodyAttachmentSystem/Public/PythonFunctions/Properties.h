#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_bodyattachmentsystem {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_characters_headless_body_workflow_bodyguideedithistory_can_undo_line_3233_965ab5fb_descriptor_json();
const char* src_core_characters_headless_body_workflow_bodyguideedithistory_can_redo_line_3237_68214687_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_bodyattachmentsystem
