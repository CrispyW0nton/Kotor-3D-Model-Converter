#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_camera {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_camera_camera_manager_cameramanager_install_all_nodes_wrapper_all_nodes_with_generated_line_258_a1a103ec_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_camera
