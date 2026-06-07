#include "PythonFunctions/Properties.h"

namespace ghostrigger::walkmesh {

const NativeFunctionImplementation& walkmeshface_color_line_151_366a94f0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Walkmesh",
        "ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshFace.color",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Walkmesh","namespace":"ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshFace.color","name":"color","callable_type":"properties","line":151,"end_line":152,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& walkmeshface_normal_line_155_2b51a16b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Walkmesh",
        "ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshFace.normal",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Walkmesh","namespace":"ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshFace.normal","name":"normal","callable_type":"properties","line":155,"end_line":165,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& walkmeshtogglecontroller_visible_line_753_0e217618_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Walkmesh",
        "ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshToggleController.visible",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Walkmesh","namespace":"ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshToggleController.visible","name":"visible","callable_type":"properties","line":753,"end_line":755,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& walkmeshtogglecontroller_key_line_814_e16bcb57_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Walkmesh",
        "ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshToggleController.key",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Walkmesh","namespace":"ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshToggleController.key","name":"key","callable_type":"properties","line":814,"end_line":816,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& walkmeshtogglecontroller_overlay_count_line_819_771599f7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Walkmesh",
        "ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer",
        "src/core/walkmesh/walkmesh_renderer.py",
        "WalkmeshToggleController.overlay_count",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Walkmesh","namespace":"ghostrigger::walkmesh::core::walkmesh::walkmesh_renderer","python_file":"src/core/walkmesh/walkmesh_renderer.py","qualname":"WalkmeshToggleController.overlay_count","name":"overlay_count","callable_type":"properties","line":819,"end_line":821,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        walkmeshface_color_line_151_366a94f0_native(),
        walkmeshface_normal_line_155_2b51a16b_native(),
        walkmeshtogglecontroller_visible_line_753_0e217618_native(),
        walkmeshtogglecontroller_key_line_814_e16bcb57_native(),
        walkmeshtogglecontroller_overlay_count_line_819_771599f7_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::walkmesh
