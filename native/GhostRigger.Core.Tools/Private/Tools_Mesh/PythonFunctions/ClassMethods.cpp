#include "Tools_Mesh/PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::meshtools {

const NativeFunctionImplementation& meshoperationresult_ok_line_42_faf3927d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools",
        "ghostrigger::core::meshtools::mesh_tools::mesh_edit_types",
        "src/mesh_tools/mesh_edit_types.py",
        "MeshOperationResult.ok",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools","namespace":"ghostrigger::core::meshtools::mesh_tools::mesh_edit_types","python_file":"src/mesh_tools/mesh_edit_types.py","qualname":"MeshOperationResult.ok","name":"ok","callable_type":"class_methods","line":42,"end_line":58,"signature":{"args":["cls","message","changed_mesh_ids","selection_changed","topology_changed","warnings"],"positional_count":2,"keyword_only_count":4,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& meshoperationresult_fail_line_61_15657c24_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools",
        "ghostrigger::core::meshtools::mesh_tools::mesh_edit_types",
        "src/mesh_tools/mesh_edit_types.py",
        "MeshOperationResult.fail",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools","namespace":"ghostrigger::core::meshtools::mesh_tools::mesh_edit_types","python_file":"src/mesh_tools/mesh_edit_types.py","qualname":"MeshOperationResult.fail","name":"fail","callable_type":"class_methods","line":61,"end_line":68,"signature":{"args":["cls","message","errors","warnings"],"positional_count":2,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& meshtopology_build_from_mesh_line_64_8c7ee68b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools",
        "ghostrigger::core::meshtools::mesh_tools::mesh_topology",
        "src/mesh_tools/mesh_topology.py",
        "MeshTopology.build_from_mesh",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools","namespace":"ghostrigger::core::meshtools::mesh_tools::mesh_topology","python_file":"src/mesh_tools/mesh_topology.py","qualname":"MeshTopology.build_from_mesh","name":"build_from_mesh","callable_type":"class_methods","line":64,"end_line":69,"signature":{"args":["cls","mesh"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& meshtopology_rebuild_after_edit_line_72_26c2a3ab_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools",
        "ghostrigger::core::meshtools::mesh_tools::mesh_topology",
        "src/mesh_tools/mesh_topology.py",
        "MeshTopology.rebuild_after_edit",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools","namespace":"ghostrigger::core::meshtools::mesh_tools::mesh_topology","python_file":"src/mesh_tools/mesh_topology.py","qualname":"MeshTopology.rebuild_after_edit","name":"rebuild_after_edit","callable_type":"class_methods","line":72,"end_line":73,"signature":{"args":["cls","mesh"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        meshoperationresult_ok_line_42_faf3927d_native(),
        meshoperationresult_fail_line_61_15657c24_native(),
        meshtopology_build_from_mesh_line_64_8c7ee68b_native(),
        meshtopology_rebuild_after_edit_line_72_26c2a3ab_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::meshtools
