#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::core::skeleton {

const NativeFunctionImplementation& bind_imported_meshes_to_skeleton_line_42_8c21e061_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "bind_imported_meshes_to_skeleton",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"bind_imported_meshes_to_skeleton","name":"bind_imported_meshes_to_skeleton","callable_type":"module_functions","line":42,"end_line":202,"signature":{"args":["model","mesh_nodes","donor_model","max_influences"],"positional_count":1,"keyword_only_count":3,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& candidate_bones_line_205_45148d86_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_candidate_bones",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_candidate_bones","name":"_candidate_bones","callable_type":"module_functions","line":205,"end_line":217,"signature":{"args":["nodes"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& is_deform_candidate_line_220_5bb32fff_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_is_deform_candidate",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_is_deform_candidate","name":"_is_deform_candidate","callable_type":"module_functions","line":220,"end_line":236,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& imported_mesh_payloads_line_239_7d29b1b1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_imported_mesh_payloads",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_imported_mesh_payloads","name":"_imported_mesh_payloads","callable_type":"module_functions","line":239,"end_line":249,"signature":{"args":["nodes"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bone_slots_line_252_dd3f0e52_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_bone_slots",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_bone_slots","name":"_bone_slots","callable_type":"module_functions","line":252,"end_line":263,"signature":{"args":["nodes","dfs_index"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& weights_for_vertex_line_266_3b24781c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_weights_for_vertex",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_weights_for_vertex","name":"_weights_for_vertex","callable_type":"module_functions","line":266,"end_line":286,"signature":{"args":["vertex","slots","max_influences"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& weights_for_vertex_with_donor_line_289_465d2469_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_weights_for_vertex_with_donor",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_weights_for_vertex_with_donor","name":"_weights_for_vertex_with_donor","callable_type":"module_functions","line":289,"end_line":304,"signature":{"args":["vertex","slots","donor_index","max_influences"],"positional_count":3,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& build_donor_vertex_index_line_307_7977e6fa_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_build_donor_vertex_index",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_build_donor_vertex_index","name":"_build_donor_vertex_index","callable_type":"module_functions","line":307,"end_line":347,"signature":{"args":["donor_model","slots","max_influences"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& map_donor_influences_to_slots_line_350_61c60ca2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_map_donor_influences_to_slots",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_map_donor_influences_to_slots","name":"_map_donor_influences_to_slots","callable_type":"module_functions","line":350,"end_line":376,"signature":{"args":["skin_row","donor_bone_map","slot_by_name","max_influences"],"positional_count":3,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& nearest_donor_vertex_line_379_543fc617_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_nearest_donor_vertex",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_nearest_donor_vertex","name":"_nearest_donor_vertex","callable_type":"module_functions","line":379,"end_line":390,"signature":{"args":["vertex","donor_index"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_influences_line_393_f4394482_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_normalize_influences",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_normalize_influences","name":"_normalize_influences","callable_type":"module_functions","line":393,"end_line":416,"signature":{"args":["influences","max_influences"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& compact_skin_bone_map_to_used_influences_line_419_b8b64074_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_compact_skin_bone_map_to_used_influences",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_compact_skin_bone_map_to_used_influences","name":"_compact_skin_bone_map_to_used_influences","callable_type":"module_functions","line":419,"end_line":484,"signature":{"args":["mesh"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& used_influence_indices_line_487_a4a04898_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_used_influence_indices",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_used_influence_indices","name":"_used_influence_indices","callable_type":"module_functions","line":487,"end_line":501,"signature":{"args":["skin_rows","bone_map_count"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& filter_parallel_list_line_504_ccc05097_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_filter_parallel_list",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_filter_parallel_list","name":"_filter_parallel_list","callable_type":"module_functions","line":504,"end_line":513,"signature":{"args":["values","indices","default"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& mesh_binding_report_line_516_49dd1ef2_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_mesh_binding_report",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_mesh_binding_report","name":"_mesh_binding_report","callable_type":"module_functions","line":516,"end_line":571,"signature":{"args":["mesh","weighting_method","quality_stage","max_influences","donor_weight_transfer","donor_vertices","fallback_vertices","donor_vertex_count","compact_report"],"positional_count":1,"keyword_only_count":8,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& transform_point_line_574_29b0bdb7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_transform_point",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_transform_point","name":"_transform_point","callable_type":"module_functions","line":574,"end_line":584,"signature":{"args":["point","origin","rotation"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& quat_rotate_vec_line_587_b17df509_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_quat_rotate_vec",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_quat_rotate_vec","name":"_quat_rotate_vec","callable_type":"module_functions","line":587,"end_line":603,"signature":{"args":["q","v"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& make_skin_node_line_606_36ea11ae_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_make_skin_node",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_make_skin_node","name":"_make_skin_node","callable_type":"module_functions","line":606,"end_line":610,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& child_positions_line_613_f85807df_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_child_positions",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_child_positions","name":"_child_positions","callable_type":"module_functions","line":613,"end_line":625,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_world_line_628_75cafaa7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_node_world",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_node_world","name":"_node_world","callable_type":"module_functions","line":628,"end_line":640,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& has_vertices_line_643_c4d17845_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_has_vertices",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_has_vertices","name":"_has_vertices","callable_type":"module_functions","line":643,"end_line":644,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& is_non_deform_hook_line_647_91e659ca_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_is_non_deform_hook",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_is_non_deform_hook","name":"_is_non_deform_hook","callable_type":"module_functions","line":647,"end_line":649,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& vec3_line_652_05721302_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_vec3",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_vec3","name":"_vec3","callable_type":"module_functions","line":652,"end_line":654,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& quat_line_657_7e1d187a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_quat",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_quat","name":"_quat","callable_type":"module_functions","line":657,"end_line":661,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& distance_line_664_46b727fc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_distance",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_distance","name":"_distance","callable_type":"module_functions","line":664,"end_line":665,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& distance_point_segment_line_668_6562c54f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Skeleton",
        "ghostrigger::core::skeleton::core::skeleton::skeleton_builder",
        "src/core/skeleton/skeleton_builder.py",
        "_distance_point_segment",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Skeleton","namespace":"ghostrigger::core::skeleton::core::skeleton::skeleton_builder","python_file":"src/core/skeleton/skeleton_builder.py","qualname":"_distance_point_segment","name":"_distance_point_segment","callable_type":"module_functions","line":668,"end_line":676,"signature":{"args":["p","a","b"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        bind_imported_meshes_to_skeleton_line_42_8c21e061_native(),
        candidate_bones_line_205_45148d86_native(),
        is_deform_candidate_line_220_5bb32fff_native(),
        imported_mesh_payloads_line_239_7d29b1b1_native(),
        bone_slots_line_252_dd3f0e52_native(),
        weights_for_vertex_line_266_3b24781c_native(),
        weights_for_vertex_with_donor_line_289_465d2469_native(),
        build_donor_vertex_index_line_307_7977e6fa_native(),
        map_donor_influences_to_slots_line_350_61c60ca2_native(),
        nearest_donor_vertex_line_379_543fc617_native(),
        normalize_influences_line_393_f4394482_native(),
        compact_skin_bone_map_to_used_influences_line_419_b8b64074_native(),
        used_influence_indices_line_487_a4a04898_native(),
        filter_parallel_list_line_504_ccc05097_native(),
        mesh_binding_report_line_516_49dd1ef2_native(),
        transform_point_line_574_29b0bdb7_native(),
        quat_rotate_vec_line_587_b17df509_native(),
        make_skin_node_line_606_36ea11ae_native(),
        child_positions_line_613_f85807df_native(),
        node_world_line_628_75cafaa7_native(),
        has_vertices_line_643_c4d17845_native(),
        is_non_deform_hook_line_647_91e659ca_native(),
        vec3_line_652_05721302_native(),
        quat_line_657_7e1d187a_native(),
        distance_line_664_46b727fc_native(),
        distance_point_segment_line_668_6562c54f_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::skeleton
