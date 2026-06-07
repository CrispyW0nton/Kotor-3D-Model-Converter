#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_kotormcp {

const char* src_kotormcp_adapters_filesystemmodellocator_load_mdx_line_401_1325659a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.adapters","python_file":"src/kotormcp/adapters.py","qualname":"FileSystemModelLocator._load_mdx","name":"_load_mdx","kind":"static_methods","line":401,"end_line":409,"signature":{"args":["mdl_path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_adapters_modelanalyzer_all_nodes_line_571_84d72b05_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.adapters","python_file":"src/kotormcp/adapters.py","qualname":"ModelAnalyzer._all_nodes","name":"_all_nodes","kind":"static_methods","line":571,"end_line":576,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_adapters_modelanalyzer_mesh_nodes_line_579_15aa35bb_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.adapters","python_file":"src/kotormcp/adapters.py","qualname":"ModelAnalyzer._mesh_nodes","name":"_mesh_nodes","kind":"static_methods","line":579,"end_line":601,"signature":{"args":["model","all_nodes"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_adapters_modelanalyzer_bone_nodes_line_604_bf59a565_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.adapters","python_file":"src/kotormcp/adapters.py","qualname":"ModelAnalyzer._bone_nodes","name":"_bone_nodes","kind":"static_methods","line":604,"end_line":608,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_adapters_modelanalyzer_bbox_line_611_69879d13_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.adapters","python_file":"src/kotormcp/adapters.py","qualname":"ModelAnalyzer._bbox","name":"_bbox","kind":"static_methods","line":611,"end_line":614,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_kotormcp_adapters_modelanalyzer_node_count_line_617_de9db12b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.adapters","python_file":"src/kotormcp/adapters.py","qualname":"ModelAnalyzer._node_count","name":"_node_count","kind":"static_methods","line":617,"end_line":622,"signature":{"args":["model","all_nodes"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/kotormcp/adapters.py", "FileSystemModelLocator._load_mdx", "static_methods", &src_kotormcp_adapters_filesystemmodellocator_load_mdx_line_401_1325659a_descriptor_json},
        {"src/kotormcp/adapters.py", "ModelAnalyzer._all_nodes", "static_methods", &src_kotormcp_adapters_modelanalyzer_all_nodes_line_571_84d72b05_descriptor_json},
        {"src/kotormcp/adapters.py", "ModelAnalyzer._mesh_nodes", "static_methods", &src_kotormcp_adapters_modelanalyzer_mesh_nodes_line_579_15aa35bb_descriptor_json},
        {"src/kotormcp/adapters.py", "ModelAnalyzer._bone_nodes", "static_methods", &src_kotormcp_adapters_modelanalyzer_bone_nodes_line_604_bf59a565_descriptor_json},
        {"src/kotormcp/adapters.py", "ModelAnalyzer._bbox", "static_methods", &src_kotormcp_adapters_modelanalyzer_bbox_line_611_69879d13_descriptor_json},
        {"src/kotormcp/adapters.py", "ModelAnalyzer._node_count", "static_methods", &src_kotormcp_adapters_modelanalyzer_node_count_line_617_de9db12b_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
