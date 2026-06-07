#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::walkmesh {

const NativeFunctionImplementation& walkmeshwriter_extract_geometry_add_vert_line_607_14e49cd1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Walkmesh",
        "ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshWriter._extract_geometry._add_vert",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Walkmesh","namespace":"ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshWriter._extract_geometry._add_vert","name":"_add_vert","callable_type":"nested_functions","line":607,"end_line":613,"signature":{"args":["v"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        walkmeshwriter_extract_geometry_add_vert_line_607_14e49cd1_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::walkmesh
