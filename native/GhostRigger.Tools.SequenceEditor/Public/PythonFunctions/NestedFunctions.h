#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_sequenceeditor {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_windows_application_core_shared_animation_workflow_animationworkflowmixin_build_baked_animation_samples_for_node_line_501_8b43e701_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_sequenceeditor
