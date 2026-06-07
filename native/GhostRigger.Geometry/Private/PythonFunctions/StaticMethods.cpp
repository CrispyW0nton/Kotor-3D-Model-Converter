#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_geometry {

const char* src_core_geometry_model_data_characterscene_node_names_line_2046_bd679a25_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene._node_names","name":"_node_names","kind":"static_methods","line":2046,"end_line":2056,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_sceneio_save_line_2352_2e457c4f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"SceneIO.save","name":"save","kind":"static_methods","line":2352,"end_line":2378,"signature":{"args":["scene","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_sceneio_load_line_2381_e2644113_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"SceneIO.load","name":"load","kind":"static_methods","line":2381,"end_line":2406,"signature":{"args":["path","load_models"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_sceneio_write_sidecar_line_2409_d2aa14fb_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"SceneIO.write_sidecar","name":"write_sidecar","kind":"static_methods","line":2409,"end_line":2429,"signature":{"args":["scene","model_path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_sceneio_find_sidecar_line_2432_2ad489d9_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"SceneIO.find_sidecar","name":"find_sidecar","kind":"static_methods","line":2432,"end_line":2437,"signature":{"args":["model_path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/geometry/model_data.py", "CharacterScene._node_names", "static_methods", &src_core_geometry_model_data_characterscene_node_names_line_2046_bd679a25_descriptor_json},
        {"src/core/geometry/model_data.py", "SceneIO.save", "static_methods", &src_core_geometry_model_data_sceneio_save_line_2352_2e457c4f_descriptor_json},
        {"src/core/geometry/model_data.py", "SceneIO.load", "static_methods", &src_core_geometry_model_data_sceneio_load_line_2381_e2644113_descriptor_json},
        {"src/core/geometry/model_data.py", "SceneIO.write_sidecar", "static_methods", &src_core_geometry_model_data_sceneio_write_sidecar_line_2409_d2aa14fb_descriptor_json},
        {"src/core/geometry/model_data.py", "SceneIO.find_sidecar", "static_methods", &src_core_geometry_model_data_sceneio_find_sidecar_line_2432_2ad489d9_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_geometry
