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

const char* src_core_camera_camera_model_ghostriggercamera_from_object_line_63_00a75f63_descriptor_json();
const char* src_core_camera_camera_model_ghostriggercamera_from_dict_line_83_1d2e8091_descriptor_json();
const char* src_core_camera_camera_render_settings_rendersettings_from_dict_line_41_2f47dc1e_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_camera
