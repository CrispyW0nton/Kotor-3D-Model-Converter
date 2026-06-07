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

const char* src_core_scene_kmax_scene_kmaxscene_asset_payload_line_61_75cc6148_descriptor_json();
const char* src_core_scene_kmax_scene_manager_kmaxscenemanager_normalize_camera_type_line_394_205df1f2_descriptor_json();
const char* src_core_scene_kmax_scene_manager_kmaxscenemanager_normalize_light_type_line_411_0362e990_descriptor_json();
const char* src_core_scene_kmax_scene_manager_kmaxscenemanager_camera_payload_line_416_dc4ef080_descriptor_json();
const char* src_core_scene_kmax_scene_manager_kmaxscenemanager_light_payload_line_425_1f04dbe5_descriptor_json();
const char* src_core_scene_kmax_serializer_kmaxserializer_validate_line_138_ebaba754_descriptor_json();
const char* src_core_scene_kmax_serializer_kmaxserializer_migrate_line_142_d4105a22_descriptor_json();
const char* src_core_scene_kmax_validator_kmaxvalidator_validate_line_28_448519b7_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_scene
