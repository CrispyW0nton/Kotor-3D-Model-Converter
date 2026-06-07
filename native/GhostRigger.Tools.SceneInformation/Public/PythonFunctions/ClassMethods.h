#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_sceneinformation {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_scene_axis_mode_axismode_from_value_line_29_43c38e4a_descriptor_json();
const char* src_core_scene_kmax_scene_kmaxscene_new_line_88_dda5f867_descriptor_json();
const char* src_core_scene_kmax_serializer_kmaxserializer_save_line_18_50cd4b7f_descriptor_json();
const char* src_core_scene_kmax_serializer_kmaxserializer_load_line_29_1667a6b4_descriptor_json();
const char* src_core_scene_kmax_serializer_kmaxserializer_to_dict_line_38_98bc0510_descriptor_json();
const char* src_core_scene_kmax_serializer_kmaxserializer_from_dict_line_65_c917e9b7_descriptor_json();
const char* src_core_scene_kmax_serializer_kmaxserializer_legacy_asset_objects_line_95_9c35044d_descriptor_json();
const char* src_core_scene_scene_manager_areproperties_from_are_data_line_352_f3e0928c_descriptor_json();
const char* src_core_scene_scene_object_transform_from_dict_line_35_68aeedb9_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_from_dict_line_88_6fd6a9f3_descriptor_json();
const char* src_core_scene_scene_object_instance_sceneobjectinstance_from_dict_line_49_531c3383_descriptor_json();
const char* src_core_scene_scene_resource_ref_sceneresourceref_from_dict_line_38_88675c01_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_sceneinformation
