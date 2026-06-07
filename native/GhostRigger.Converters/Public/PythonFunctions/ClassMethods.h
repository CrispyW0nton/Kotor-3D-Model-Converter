#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_converters {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_converters_mesh_converter_objexporter_is_facial_geometry_line_535_594fa6cf_descriptor_json();
const char* src_converters_mesh_converter_objexporter_is_deformation_helper_line_574_cc6f545f_descriptor_json();
const char* src_converters_mesh_converter_objexporter_is_renderable_line_623_01a547cf_descriptor_json();
const char* src_converters_normal_map_txibuilder_normal_map_preset_line_134_faf7d193_descriptor_json();
const char* src_converters_normal_map_txibuilder_envmap_preset_line_142_f3d3c78b_descriptor_json();
const char* src_converters_normal_map_txibuilder_diffuse_preset_line_147_1291f1af_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_converters
