#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_kotormcp {

const char* src_kotormcp_tools_debug_skinning_debugsession_load_model_depth_line_288_7527285a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.tools.debug_skinning","python_file":"src/kotormcp/tools/debug_skinning.py","qualname":"_DebugSession.load_model._depth","name":"_depth","kind":"nested_functions","line":288,"end_line":292,"signature":{"args":["nd","d"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_tools_debug_skinning_debugsession_get_bone_hierarchy_build_tree_line_606_3daacf2b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.tools.debug_skinning","python_file":"src/kotormcp/tools/debug_skinning.py","qualname":"_DebugSession.get_bone_hierarchy._build_tree","name":"_build_tree","kind":"nested_functions","line":606,"end_line":616,"signature":{"args":["node","depth"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_tools_ghostrigger_tools_close_quat_close_line_104_b36abb8a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.tools.ghostrigger_tools","python_file":"src/kotormcp/tools/ghostrigger_tools.py","qualname":"_close_quat.close","name":"close","kind":"nested_functions","line":104,"end_line":105,"signature":{"args":["sign"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_tools_ghostrigger_tools_compare_model_pipelines_add_line_261_5b32c5d1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.tools.ghostrigger_tools","python_file":"src/kotormcp/tools/ghostrigger_tools.py","qualname":"compare_model_pipelines.add","name":"add","kind":"nested_functions","line":261,"end_line":265,"signature":{"args":["field","pykotor","ghostrigger"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/kotormcp/tools/debug_skinning.py", "_DebugSession.load_model._depth", "nested_functions", &src_kotormcp_tools_debug_skinning_debugsession_load_model_depth_line_288_7527285a_descriptor_json},
        {"src/kotormcp/tools/debug_skinning.py", "_DebugSession.get_bone_hierarchy._build_tree", "nested_functions", &src_kotormcp_tools_debug_skinning_debugsession_get_bone_hierarchy_build_tree_line_606_3daacf2b_descriptor_json},
        {"src/kotormcp/tools/ghostrigger_tools.py", "_close_quat.close", "nested_functions", &src_kotormcp_tools_ghostrigger_tools_close_quat_close_line_104_b36abb8a_descriptor_json},
        {"src/kotormcp/tools/ghostrigger_tools.py", "compare_model_pipelines.add", "nested_functions", &src_kotormcp_tools_ghostrigger_tools_compare_model_pipelines_add_line_261_5b32c5d1_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
