#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_scene {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_scene_scene_manager_frustum_update_from_matrix_plane_line_139_e5dad599_descriptor_json();
const char* src_core_scene_scene_manager_frustum_update_from_camera_plane_through_pos_line_198_93dc44e6_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_scene
