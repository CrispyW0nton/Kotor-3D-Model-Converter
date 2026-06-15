#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::domain::core::scene {

const NativeFunctionImplementation& frustum_update_from_matrix_plane_line_139_e5dad599_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Scene",
        "ghostrigger::domain::core::scene::core::scene::scene_manager",
        "src/core/scene/scene_manager.py",
        "Frustum.update_from_matrix._plane",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Scene","namespace":"ghostrigger::domain::core::scene::core::scene::scene_manager","python_file":"src/core/scene/scene_manager.py","qualname":"Frustum.update_from_matrix._plane","name":"_plane","callable_type":"nested_functions","line":139,"end_line":145,"signature":{"args":["row_a","row_b","sign"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& frustum_update_from_camera_plane_through_pos_line_198_93dc44e6_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Scene",
        "ghostrigger::domain::core::scene::core::scene::scene_manager",
        "src/core/scene/scene_manager.py",
        "Frustum.update_from_camera._plane_through_pos",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Scene","namespace":"ghostrigger::domain::core::scene::core::scene::scene_manager","python_file":"src/core/scene/scene_manager.py","qualname":"Frustum.update_from_camera._plane_through_pos","name":"_plane_through_pos","callable_type":"nested_functions","line":198,"end_line":202,"signature":{"args":["n"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        frustum_update_from_matrix_plane_line_139_e5dad599_native(),
        frustum_update_from_camera_plane_through_pos_line_198_93dc44e6_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::scene
