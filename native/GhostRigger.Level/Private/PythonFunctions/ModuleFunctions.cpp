#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_level {

const char* src_core_level_kmap_model_utc_now_iso_line_19_f20cd66e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Level","python_module":"src.core.level.kmap_model","python_file":"src/core/level/kmap_model.py","qualname":"utc_now_iso","name":"utc_now_iso","kind":"module_functions","line":19,"end_line":20,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_level_kmap_model_stable_id_line_23_5bbc0cf4_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Level","python_module":"src.core.level.kmap_model","python_file":"src/core/level/kmap_model.py","qualname":"stable_id","name":"stable_id","kind":"module_functions","line":23,"end_line":24,"signature":{"args":["prefix"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_level_kmap_model_vec3_line_27_72d6d689_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Level","python_module":"src.core.level.kmap_model","python_file":"src/core/level/kmap_model.py","qualname":"_vec3","name":"_vec3","kind":"module_functions","line":27,"end_line":35,"signature":{"args":["value","default"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_level_kmap_model_dict_line_38_e0df7116_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Level","python_module":"src.core.level.kmap_model","python_file":"src/core/level/kmap_model.py","qualname":"_dict","name":"_dict","kind":"module_functions","line":38,"end_line":39,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_level_kmap_model_new_kmap_project_line_359_3fc4d07f_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Level","python_module":"src.core.level.kmap_model","python_file":"src/core/level/kmap_model.py","qualname":"new_kmap_project","name":"new_kmap_project","kind":"module_functions","line":359,"end_line":367,"signature":{"args":["name","game","author"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_level_level_manifest_build_level_manifest_line_12_f6f49199_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Level","python_module":"src.core.level.level_manifest","python_file":"src/core/level/level_manifest.py","qualname":"build_level_manifest","name":"build_level_manifest","kind":"module_functions","line":12,"end_line":39,"signature":{"args":["project","kmap_path","export_paths","issues"],"positional_count":1,"keyword_only_count":3,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/level/kmap_model.py", "utc_now_iso", "module_functions", &src_core_level_kmap_model_utc_now_iso_line_19_f20cd66e_descriptor_json},
        {"src/core/level/kmap_model.py", "stable_id", "module_functions", &src_core_level_kmap_model_stable_id_line_23_5bbc0cf4_descriptor_json},
        {"src/core/level/kmap_model.py", "_vec3", "module_functions", &src_core_level_kmap_model_vec3_line_27_72d6d689_descriptor_json},
        {"src/core/level/kmap_model.py", "_dict", "module_functions", &src_core_level_kmap_model_dict_line_38_e0df7116_descriptor_json},
        {"src/core/level/kmap_model.py", "new_kmap_project", "module_functions", &src_core_level_kmap_model_new_kmap_project_line_359_3fc4d07f_descriptor_json},
        {"src/core/level/level_manifest.py", "build_level_manifest", "module_functions", &src_core_level_level_manifest_build_level_manifest_line_12_f6f49199_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_level
