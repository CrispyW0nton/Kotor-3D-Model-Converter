#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_level {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_level_kmap_model_leveltransform_from_dict_line_49_1ea35e51_descriptor_json();
const char* src_core_level_kmap_model_walkmeshreference_from_dict_line_77_7fa286f9_descriptor_json();
const char* src_core_level_kmap_model_roominstance_from_dict_line_120_da85e907_descriptor_json();
const char* src_core_level_kmap_model_moduleinstance_from_dict_line_172_68333948_descriptor_json();
const char* src_core_level_kmap_model_blueprintentry_from_dict_line_218_4e37aafd_descriptor_json();
const char* src_core_level_kmap_model_texturereference_from_dict_line_255_862fc274_descriptor_json();
const char* src_core_level_kmap_model_materialreference_from_dict_line_289_228b1ab3_descriptor_json();
const char* src_core_level_kmap_serializer_kmapserializer_load_line_28_e5a2fa68_descriptor_json();
const char* src_core_level_kmap_serializer_kmapserializer_save_line_40_3982bcf2_descriptor_json();
const char* src_core_level_kmap_serializer_kmapserializer_validate_schema_line_51_2ab5f475_descriptor_json();
const char* src_core_level_kmap_serializer_kmapserializer_migrate_line_75_43020a99_descriptor_json();
const char* src_core_level_kmap_serializer_kmapserializer_from_dict_line_84_6823bdcb_descriptor_json();
const char* src_core_level_kmap_serializer_kmapserializer_to_dict_line_141_8a731e1d_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_level
