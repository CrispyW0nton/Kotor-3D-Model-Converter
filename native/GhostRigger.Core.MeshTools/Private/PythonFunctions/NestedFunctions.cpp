#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::meshtools {

const NativeFunctionImplementation& cluster_vertices_find_line_60_b7051c5a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.MeshTools",
        "ghostrigger::core::meshtools::mesh_tools::mesh_weld",
        "src/mesh_tools/mesh_weld.py",
        "_cluster_vertices.find",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.MeshTools","namespace":"ghostrigger::core::meshtools::mesh_tools::mesh_weld","python_file":"src/mesh_tools/mesh_weld.py","qualname":"_cluster_vertices.find","name":"find","callable_type":"nested_functions","line":60,"end_line":64,"signature":{"args":["x"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cluster_vertices_union_line_66_9b38cc0d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.MeshTools",
        "ghostrigger::core::meshtools::mesh_tools::mesh_weld",
        "src/mesh_tools/mesh_weld.py",
        "_cluster_vertices.union",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.MeshTools","namespace":"ghostrigger::core::meshtools::mesh_tools::mesh_weld","python_file":"src/mesh_tools/mesh_weld.py","qualname":"_cluster_vertices.union","name":"union","callable_type":"nested_functions","line":66,"end_line":69,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        cluster_vertices_find_line_60_b7051c5a_native(),
        cluster_vertices_union_line_66_9b38cc0d_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::meshtools
