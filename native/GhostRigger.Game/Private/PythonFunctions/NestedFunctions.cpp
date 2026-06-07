#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_game {

const char* src_core_game_kotor_loader_read_mesh_safe_vec3_list_line_776_3a830960_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Game","python_module":"src.core.game.kotor_loader","python_file":"src/core/game/kotor_loader.py","qualname":"_read_mesh._safe_vec3_list","name":"_safe_vec3_list","kind":"nested_functions","line":776,"end_line":782,"signature":{"args":["attr_val"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_game_kotor_loader_read_mesh_safe_vec2_list_line_784_a5cd70ac_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Game","python_module":"src.core.game.kotor_loader","python_file":"src/core/game/kotor_loader.py","qualname":"_read_mesh._safe_vec2_list","name":"_safe_vec2_list","kind":"nested_functions","line":784,"end_line":790,"signature":{"args":["attr_val"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_game_kotor_loader_read_mesh_safe_float_line_809_85bd8cf1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Game","python_module":"src.core.game.kotor_loader","python_file":"src/core/game/kotor_loader.py","qualname":"_read_mesh._safe_float","name":"_safe_float","kind":"nested_functions","line":809,"end_line":813,"signature":{"args":["x","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_game_kotor_loader_read_mesh_safe_uv_line_815_aa513aa1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Game","python_module":"src.core.game.kotor_loader","python_file":"src/core/game/kotor_loader.py","qualname":"_read_mesh._safe_uv","name":"_safe_uv","kind":"nested_functions","line":815,"end_line":819,"signature":{"args":["x","y"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_game_pykotor_mdl_io_fix_ghostrigger_trimesh_read_read_i32_as_u32_line_367_d948baad_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Game","python_module":"src.core.game.pykotor_mdl_io_fix","python_file":"src/core/game/pykotor_mdl_io_fix.py","qualname":"_ghostrigger_trimesh_read._read_i32_as_u32","name":"_read_i32_as_u32","kind":"nested_functions","line":367,"end_line":369,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/game/kotor_loader.py", "_read_mesh._safe_vec3_list", "nested_functions", &src_core_game_kotor_loader_read_mesh_safe_vec3_list_line_776_3a830960_descriptor_json},
        {"src/core/game/kotor_loader.py", "_read_mesh._safe_vec2_list", "nested_functions", &src_core_game_kotor_loader_read_mesh_safe_vec2_list_line_784_a5cd70ac_descriptor_json},
        {"src/core/game/kotor_loader.py", "_read_mesh._safe_float", "nested_functions", &src_core_game_kotor_loader_read_mesh_safe_float_line_809_85bd8cf1_descriptor_json},
        {"src/core/game/kotor_loader.py", "_read_mesh._safe_uv", "nested_functions", &src_core_game_kotor_loader_read_mesh_safe_uv_line_815_aa513aa1_descriptor_json},
        {"src/core/game/pykotor_mdl_io_fix.py", "_ghostrigger_trimesh_read._read_i32_as_u32", "nested_functions", &src_core_game_pykotor_mdl_io_fix_ghostrigger_trimesh_read_read_i32_as_u32_line_367_d948baad_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_game
