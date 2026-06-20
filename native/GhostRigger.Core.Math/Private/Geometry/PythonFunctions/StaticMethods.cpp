#include "Geometry/PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::geometry {

const NativeFunctionImplementation& characterscene_node_names_line_2046_bd679a25_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "CharacterScene._node_names",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"CharacterScene._node_names","name":"_node_names","callable_type":"static_methods","line":2046,"end_line":2056,"signature":{"args":["model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& sceneio_save_line_2352_2e457c4f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "SceneIO.save",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"SceneIO.save","name":"save","callable_type":"static_methods","line":2352,"end_line":2378,"signature":{"args":["scene","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& sceneio_load_line_2381_e2644113_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "SceneIO.load",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"SceneIO.load","name":"load","callable_type":"static_methods","line":2381,"end_line":2406,"signature":{"args":["path","load_models"],"positional_count":1,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& sceneio_write_sidecar_line_2409_d2aa14fb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "SceneIO.write_sidecar",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"SceneIO.write_sidecar","name":"write_sidecar","callable_type":"static_methods","line":2409,"end_line":2429,"signature":{"args":["scene","model_path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& sceneio_find_sidecar_line_2432_2ad489d9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Math",
        "ghostrigger::core::geometry::core::geometry::model_data",
        "src/core/geometry/model_data.py",
        "SceneIO.find_sidecar",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Math","namespace":"ghostrigger::core::geometry::core::geometry::model_data","python_file":"src/core/geometry/model_data.py","qualname":"SceneIO.find_sidecar","name":"find_sidecar","callable_type":"static_methods","line":2432,"end_line":2437,"signature":{"args":["model_path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        characterscene_node_names_line_2046_bd679a25_native(),
        sceneio_save_line_2352_2e457c4f_native(),
        sceneio_load_line_2381_e2644113_native(),
        sceneio_write_sidecar_line_2409_d2aa14fb_native(),
        sceneio_find_sidecar_line_2432_2ad489d9_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::geometry
