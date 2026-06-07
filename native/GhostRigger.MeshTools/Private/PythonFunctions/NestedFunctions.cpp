#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_meshtools {

const char* src_mesh_tools_mesh_weld_cluster_vertices_find_line_60_b7051c5a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MeshTools","python_module":"src.mesh_tools.mesh_weld","python_file":"src/mesh_tools/mesh_weld.py","qualname":"_cluster_vertices.find","name":"find","kind":"nested_functions","line":60,"end_line":64,"signature":{"args":["x"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_mesh_tools_mesh_weld_cluster_vertices_union_line_66_9b38cc0d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.MeshTools","python_module":"src.mesh_tools.mesh_weld","python_file":"src/mesh_tools/mesh_weld.py","qualname":"_cluster_vertices.union","name":"union","kind":"nested_functions","line":66,"end_line":69,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/mesh_tools/mesh_weld.py", "_cluster_vertices.find", "nested_functions", &src_mesh_tools_mesh_weld_cluster_vertices_find_line_60_b7051c5a_descriptor_json},
        {"src/mesh_tools/mesh_weld.py", "_cluster_vertices.union", "nested_functions", &src_mesh_tools_mesh_weld_cluster_vertices_union_line_66_9b38cc0d_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_meshtools
