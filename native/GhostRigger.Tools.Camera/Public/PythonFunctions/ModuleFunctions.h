#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_camera {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_camera_render_manifest_append_render_manifest_line_24_1e0aa46a_descriptor_json();
const char* src_gui_camera_init_getattr_line_19_bd15a5bb_descriptor_json();
const char* src_gui_camera_init_dir_line_28_8f929c2b_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_camera
