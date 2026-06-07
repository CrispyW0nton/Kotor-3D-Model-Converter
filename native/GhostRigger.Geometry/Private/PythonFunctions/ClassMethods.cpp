#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_geometry {

const char* src_core_geometry_model_data_kotormodel_load_line_1713_06efb4df_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"KotorModel.load","name":"load","kind":"class_methods","line":1713,"end_line":1734,"signature":{"args":["cls","mdl_path","mdx_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_characterscene_hook_list_for_line_2059_3faac002_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene._hook_list_for","name":"_hook_list_for","kind":"class_methods","line":2059,"end_line":2069,"signature":{"args":["cls","model"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_characterscene_facial_bone_list_for_line_2072_1a08165b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene._facial_bone_list_for","name":"_facial_bone_list_for","kind":"class_methods","line":2072,"end_line":2081,"signature":{"args":["cls","model"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_characterscene_from_dict_line_2196_7e1623ef_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene.from_dict","name":"from_dict","kind":"class_methods","line":2196,"end_line":2306,"signature":{"args":["cls","data","load_models"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_geometry_model_data_characterscene_from_json_line_2314_e011a172_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Geometry","python_module":"src.core.geometry.model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene.from_json","name":"from_json","kind":"class_methods","line":2314,"end_line":2317,"signature":{"args":["cls","text","load_models"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/geometry/model_data.py", "KotorModel.load", "class_methods", &src_core_geometry_model_data_kotormodel_load_line_1713_06efb4df_descriptor_json},
        {"src/core/geometry/model_data.py", "CharacterScene._hook_list_for", "class_methods", &src_core_geometry_model_data_characterscene_hook_list_for_line_2059_3faac002_descriptor_json},
        {"src/core/geometry/model_data.py", "CharacterScene._facial_bone_list_for", "class_methods", &src_core_geometry_model_data_characterscene_facial_bone_list_for_line_2072_1a08165b_descriptor_json},
        {"src/core/geometry/model_data.py", "CharacterScene.from_dict", "class_methods", &src_core_geometry_model_data_characterscene_from_dict_line_2196_7e1623ef_descriptor_json},
        {"src/core/geometry/model_data.py", "CharacterScene.from_json", "class_methods", &src_core_geometry_model_data_characterscene_from_json_line_2314_e011a172_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_geometry
