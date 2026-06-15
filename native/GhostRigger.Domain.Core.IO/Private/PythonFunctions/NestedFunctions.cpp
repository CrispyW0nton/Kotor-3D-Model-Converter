#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::domain::core::io {

const NativeFunctionImplementation& fbx_mesh_to_gr_mesh_add_poly_vertex_line_172_858003db_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.IO",
        "ghostrigger::domain::core::io::fbx::fbx_scene_adapter",
        "src/io/fbx/fbx_scene_adapter.py",
        "fbx_mesh_to_gr_mesh.add_poly_vertex",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.IO","namespace":"ghostrigger::domain::core::io::fbx::fbx_scene_adapter","python_file":"src/io/fbx/fbx_scene_adapter.py","qualname":"fbx_mesh_to_gr_mesh.add_poly_vertex","name":"add_poly_vertex","callable_type":"nested_functions","line":172,"end_line":200,"signature":{"args":["poly_index","corner"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        fbx_mesh_to_gr_mesh_add_poly_vertex_line_172_858003db_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::io
