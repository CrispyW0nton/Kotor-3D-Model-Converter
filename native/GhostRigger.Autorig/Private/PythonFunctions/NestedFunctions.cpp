#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_autorig {

const char* src_autorig_accurig_guideplacer_place_guides_clamp_line_327_5bc55e06_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.accurig","python_file":"src/autorig/accurig.py","qualname":"GuidePlacer.place_guides._clamp","name":"_clamp","kind":"nested_functions","line":327,"end_line":328,"signature":{"args":["x","lo","hi"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_auto_rigger_rigextractor_extract_index_line_335_1c027174_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.auto_rigger","python_file":"src/autorig/auto_rigger.py","qualname":"RigExtractor.extract._index","name":"_index","kind":"nested_functions","line":335,"end_line":338,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_auto_rigger_rigextractor_extract_add_bone_line_360_fa66f26c_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.auto_rigger","python_file":"src/autorig/auto_rigger.py","qualname":"RigExtractor.extract._add_bone","name":"_add_bone","kind":"nested_functions","line":360,"end_line":379,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_auto_rigger_rigextractor_extract_walk_dummies_line_382_b4c5b65c_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.auto_rigger","python_file":"src/autorig/auto_rigger.py","qualname":"RigExtractor.extract._walk_dummies","name":"_walk_dummies","kind":"nested_functions","line":382,"end_line":386,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_auto_rigger_autorigger_bind_pose_from_fbx_bones_norm_line_872_52f30d34_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.auto_rigger","python_file":"src/autorig/auto_rigger.py","qualname":"AutoRigger.bind_pose_from_fbx_bones._norm","name":"_norm","kind":"nested_functions","line":872,"end_line":876,"signature":{"args":["s"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_autorig_retarget_engine_meshscaler_apply_scale_node_line_493_fdfe78ca_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Autorig","python_module":"src.autorig.retarget_engine","python_file":"src/autorig/retarget_engine.py","qualname":"MeshScaler.apply._scale_node","name":"_scale_node","kind":"nested_functions","line":493,"end_line":516,"signature":{"args":["n"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/autorig/accurig.py", "GuidePlacer.place_guides._clamp", "nested_functions", &src_autorig_accurig_guideplacer_place_guides_clamp_line_327_5bc55e06_descriptor_json},
        {"src/autorig/auto_rigger.py", "RigExtractor.extract._index", "nested_functions", &src_autorig_auto_rigger_rigextractor_extract_index_line_335_1c027174_descriptor_json},
        {"src/autorig/auto_rigger.py", "RigExtractor.extract._add_bone", "nested_functions", &src_autorig_auto_rigger_rigextractor_extract_add_bone_line_360_fa66f26c_descriptor_json},
        {"src/autorig/auto_rigger.py", "RigExtractor.extract._walk_dummies", "nested_functions", &src_autorig_auto_rigger_rigextractor_extract_walk_dummies_line_382_b4c5b65c_descriptor_json},
        {"src/autorig/auto_rigger.py", "AutoRigger.bind_pose_from_fbx_bones._norm", "nested_functions", &src_autorig_auto_rigger_autorigger_bind_pose_from_fbx_bones_norm_line_872_52f30d34_descriptor_json},
        {"src/autorig/retarget_engine.py", "MeshScaler.apply._scale_node", "nested_functions", &src_autorig_retarget_engine_meshscaler_apply_scale_node_line_493_fdfe78ca_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_autorig
