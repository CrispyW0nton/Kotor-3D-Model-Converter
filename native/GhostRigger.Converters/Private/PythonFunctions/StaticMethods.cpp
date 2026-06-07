#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_converters {

const char* src_converters_mesh_converter_objexporter_clean_tex_line_498_52c0af98_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"OBJExporter._clean_tex","name":"_clean_tex","kind":"static_methods","line":498,"end_line":503,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_mesh_converter_objexporter_node_bind_world_verts_line_650_d03ab6eb_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"OBJExporter._node_bind_world_verts","name":"_node_bind_world_verts","kind":"static_methods","line":650,"end_line":692,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_mesh_converter_objexporter_node_bind_world_normals_line_695_d85a26c8_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"OBJExporter._node_bind_world_normals","name":"_node_bind_world_normals","kind":"static_methods","line":695,"end_line":712,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_mesh_converter_objexporter_export_textures_to_dir_line_886_657b24bf_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"OBJExporter._export_textures_to_dir","name":"_export_textures_to_dir","kind":"static_methods","line":886,"end_line":915,"signature":{"args":["model","out_dir","tex_cache"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_mesh_converter_objexporter_export_baked_lightmaps_to_dir_line_918_79da02c3_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"OBJExporter._export_baked_lightmaps_to_dir","name":"_export_baked_lightmaps_to_dir","kind":"static_methods","line":918,"end_line":945,"signature":{"args":["model","out_dir"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_mesh_converter_gltfexporter_tex_to_base64_uri_line_3260_857d474d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"GLTFExporter._tex_to_base64_uri","name":"_tex_to_base64_uri","kind":"static_methods","line":3260,"end_line":3278,"signature":{"args":["tex_cache","tex_name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/converters/mesh_converter.py", "OBJExporter._clean_tex", "static_methods", &src_converters_mesh_converter_objexporter_clean_tex_line_498_52c0af98_descriptor_json},
        {"src/converters/mesh_converter.py", "OBJExporter._node_bind_world_verts", "static_methods", &src_converters_mesh_converter_objexporter_node_bind_world_verts_line_650_d03ab6eb_descriptor_json},
        {"src/converters/mesh_converter.py", "OBJExporter._node_bind_world_normals", "static_methods", &src_converters_mesh_converter_objexporter_node_bind_world_normals_line_695_d85a26c8_descriptor_json},
        {"src/converters/mesh_converter.py", "OBJExporter._export_textures_to_dir", "static_methods", &src_converters_mesh_converter_objexporter_export_textures_to_dir_line_886_657b24bf_descriptor_json},
        {"src/converters/mesh_converter.py", "OBJExporter._export_baked_lightmaps_to_dir", "static_methods", &src_converters_mesh_converter_objexporter_export_baked_lightmaps_to_dir_line_918_79da02c3_descriptor_json},
        {"src/converters/mesh_converter.py", "GLTFExporter._tex_to_base64_uri", "static_methods", &src_converters_mesh_converter_gltfexporter_tex_to_base64_uri_line_3260_857d474d_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_converters
