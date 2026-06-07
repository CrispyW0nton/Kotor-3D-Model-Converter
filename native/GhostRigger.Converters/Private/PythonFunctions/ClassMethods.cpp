#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_converters {

const char* src_converters_mesh_converter_objexporter_is_facial_geometry_line_535_594fa6cf_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"OBJExporter._is_facial_geometry","name":"_is_facial_geometry","kind":"class_methods","line":535,"end_line":571,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_mesh_converter_objexporter_is_deformation_helper_line_574_cc6f545f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"OBJExporter._is_deformation_helper","name":"_is_deformation_helper","kind":"class_methods","line":574,"end_line":620,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_mesh_converter_objexporter_is_renderable_line_623_01a547cf_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.mesh_converter","python_file":"src/converters/mesh_converter.py","qualname":"OBJExporter._is_renderable","name":"_is_renderable","kind":"class_methods","line":623,"end_line":645,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_normal_map_txibuilder_normal_map_preset_line_134_faf7d193_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.normal_map","python_file":"src/converters/normal_map.py","qualname":"TXIBuilder.normal_map_preset","name":"normal_map_preset","kind":"class_methods","line":134,"end_line":139,"signature":{"args":["cls","bump_scale"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_normal_map_txibuilder_envmap_preset_line_142_f3d3c78b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.normal_map","python_file":"src/converters/normal_map.py","qualname":"TXIBuilder.envmap_preset","name":"envmap_preset","kind":"class_methods","line":142,"end_line":144,"signature":{"args":["cls"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_converters_normal_map_txibuilder_diffuse_preset_line_147_1291f1af_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Converters","python_module":"src.converters.normal_map","python_file":"src/converters/normal_map.py","qualname":"TXIBuilder.diffuse_preset","name":"diffuse_preset","kind":"class_methods","line":147,"end_line":149,"signature":{"args":["cls"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/converters/mesh_converter.py", "OBJExporter._is_facial_geometry", "class_methods", &src_converters_mesh_converter_objexporter_is_facial_geometry_line_535_594fa6cf_descriptor_json},
        {"src/converters/mesh_converter.py", "OBJExporter._is_deformation_helper", "class_methods", &src_converters_mesh_converter_objexporter_is_deformation_helper_line_574_cc6f545f_descriptor_json},
        {"src/converters/mesh_converter.py", "OBJExporter._is_renderable", "class_methods", &src_converters_mesh_converter_objexporter_is_renderable_line_623_01a547cf_descriptor_json},
        {"src/converters/normal_map.py", "TXIBuilder.normal_map_preset", "class_methods", &src_converters_normal_map_txibuilder_normal_map_preset_line_134_faf7d193_descriptor_json},
        {"src/converters/normal_map.py", "TXIBuilder.envmap_preset", "class_methods", &src_converters_normal_map_txibuilder_envmap_preset_line_142_f3d3c78b_descriptor_json},
        {"src/converters/normal_map.py", "TXIBuilder.diffuse_preset", "class_methods", &src_converters_normal_map_txibuilder_diffuse_preset_line_147_1291f1af_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_converters
