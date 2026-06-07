#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_io {

const char* src_io_fbx_fbx_scene_adapter_fbx_mesh_to_gr_mesh_add_poly_vertex_line_172_858003db_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.IO","python_module":"src.io.fbx.fbx_scene_adapter","python_file":"src/io/fbx/fbx_scene_adapter.py","qualname":"fbx_mesh_to_gr_mesh.add_poly_vertex","name":"add_poly_vertex","kind":"nested_functions","line":172,"end_line":200,"signature":{"args":["poly_index","corner"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/io/fbx/fbx_scene_adapter.py", "fbx_mesh_to_gr_mesh.add_poly_vertex", "nested_functions", &src_io_fbx_fbx_scene_adapter_fbx_mesh_to_gr_mesh_add_poly_vertex_line_172_858003db_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_io
