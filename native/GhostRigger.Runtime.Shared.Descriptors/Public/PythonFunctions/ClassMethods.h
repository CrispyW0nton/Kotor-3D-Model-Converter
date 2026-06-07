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

const char* src_core_project_resource_address_resourceaddress_from_dict_line_87_734cf9ce_descriptor_json();
const char* src_core_scene_scene_object_transform_from_dict_line_35_68aeedb9_descriptor_json();
const char* src_core_scene_scene_object_pivotdata_from_dict_line_88_6fd6a9f3_descriptor_json();
const char* src_core_scene_scene_object_instance_sceneobjectinstance_from_dict_line_49_531c3383_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_runtime_shared_descriptors
