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

const char* src_converters_mesh_converter_objexporter_clean_tex_line_498_52c0af98_descriptor_json();
const char* src_converters_mesh_converter_objexporter_node_bind_world_verts_line_650_d03ab6eb_descriptor_json();
const char* src_converters_mesh_converter_objexporter_node_bind_world_normals_line_695_d85a26c8_descriptor_json();
const char* src_converters_mesh_converter_objexporter_export_textures_to_dir_line_886_657b24bf_descriptor_json();
const char* src_converters_mesh_converter_objexporter_export_baked_lightmaps_to_dir_line_918_79da02c3_descriptor_json();
const char* src_converters_mesh_converter_gltfexporter_tex_to_base64_uri_line_3260_857d474d_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_converters
