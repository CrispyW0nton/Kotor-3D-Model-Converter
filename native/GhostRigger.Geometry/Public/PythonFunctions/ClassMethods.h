#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_geometry {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_geometry_model_data_kotormodel_load_line_1713_06efb4df_descriptor_json();
const char* src_core_geometry_model_data_characterscene_hook_list_for_line_2059_3faac002_descriptor_json();
const char* src_core_geometry_model_data_characterscene_facial_bone_list_for_line_2072_1a08165b_descriptor_json();
const char* src_core_geometry_model_data_characterscene_from_dict_line_2196_7e1623ef_descriptor_json();
const char* src_core_geometry_model_data_characterscene_from_json_line_2314_e011a172_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_geometry
