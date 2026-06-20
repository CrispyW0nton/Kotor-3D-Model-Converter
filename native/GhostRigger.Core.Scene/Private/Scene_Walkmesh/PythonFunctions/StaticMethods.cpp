#include "Scene_Walkmesh/PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::walkmesh {

const NativeFunctionImplementation& walkmeshwriter_roundtrip_line_568_cd29482e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Scene",
        "ghostrigger::core::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshWriter.roundtrip",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Scene","namespace":"ghostrigger::core::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshWriter.roundtrip","name":"roundtrip","callable_type":"static_methods","line":568,"end_line":582,"signature":{"args":["overlay"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& walkmeshwriter_compute_adjacency_line_631_816fefe7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Scene",
        "ghostrigger::core::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshWriter._compute_adjacency",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Scene","namespace":"ghostrigger::core::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshWriter._compute_adjacency","name":"_compute_adjacency","callable_type":"static_methods","line":631,"end_line":662,"signature":{"args":["face_triples"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& walkmeshwriter_pack_line_665_044477c6_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Scene",
        "ghostrigger::core::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshWriter._pack",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Scene","namespace":"ghostrigger::core::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshWriter._pack","name":"_pack","callable_type":"static_methods","line":665,"end_line":709,"signature":{"args":["verts","faces","materials","adjacencies"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        walkmeshwriter_roundtrip_line_568_cd29482e_native(),
        walkmeshwriter_compute_adjacency_line_631_816fefe7_native(),
        walkmeshwriter_pack_line_665_044477c6_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::walkmesh
