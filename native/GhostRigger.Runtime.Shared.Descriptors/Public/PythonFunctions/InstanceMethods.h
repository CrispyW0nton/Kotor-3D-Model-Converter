#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_project_resource_address_resourceaddress_post_init_line_57_2af13706_descriptor_json();
const char* src_core_project_resource_address_resourceaddress_to_dict_line_72_4e4775e5_descriptor_json();
const char* src_core_project_resource_address_resourceaddress_stable_key_line_105_f62055fd_descriptor_json();
const char* src_core_project_resource_address_resourceaddress_display_name_line_147_9fa30e20_descriptor_json();
const char* src_core_scene_scene_object_transform_to_dict_line_27_0e4c5c8d_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_position_line_58_a41b1041_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_rotation_line_66_052837bd_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_is_valid_line_69_52cd01cc_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_sanitized_line_73_9bbd75d0_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_to_dict_line_78_3048ea00_descriptor_json();
const char* src_core_scene_scene_object_instance_sceneobjectinstance_to_dict_line_27_564c9705_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors
