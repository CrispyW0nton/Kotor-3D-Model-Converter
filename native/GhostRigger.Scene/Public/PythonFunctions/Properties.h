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

const char* src_core_scene_axis_mode_axismode_label_line_25_7f940ea5_descriptor_json();
const char* src_core_scene_kmax_scene_kmaxscene_display_name_line_43_4c4f5179_descriptor_json();
const char* src_core_scene_module_scene_import_moduleroomplacement_group_id_line_26_2739f71f_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_position_line_54_fa472186_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_rotation_line_62_8f4a7cea_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_scene
