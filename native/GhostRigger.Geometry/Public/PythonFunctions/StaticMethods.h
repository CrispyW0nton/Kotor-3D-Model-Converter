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

const char* src_core_geometry_model_data_characterscene_node_names_line_2046_bd679a25_descriptor_json();
const char* src_core_geometry_model_data_sceneio_save_line_2352_2e457c4f_descriptor_json();
const char* src_core_geometry_model_data_sceneio_load_line_2381_e2644113_descriptor_json();
const char* src_core_geometry_model_data_sceneio_write_sidecar_line_2409_d2aa14fb_descriptor_json();
const char* src_core_geometry_model_data_sceneio_find_sidecar_line_2432_2ad489d9_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_geometry
