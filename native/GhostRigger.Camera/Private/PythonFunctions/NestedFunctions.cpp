#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::camera {

const NativeFunctionImplementation& cameramanager_install_all_nodes_wrapper_all_nodes_with_generated_line_258_a1a103ec_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Camera",
        "ghostrigger::camera::core::camera::camera_manager",
        "src/core/camera/camera_manager.py",
        "CameraManager._install_all_nodes_wrapper._all_nodes_with_generated",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Camera","namespace":"ghostrigger::camera::core::camera::camera_manager","python_file":"src/core/camera/camera_manager.py","qualname":"CameraManager._install_all_nodes_wrapper._all_nodes_with_generated","name":"_all_nodes_with_generated","callable_type":"nested_functions","line":258,"end_line":263,"signature":{"args":["_model"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        cameramanager_install_all_nodes_wrapper_all_nodes_with_generated_line_258_a1a103ec_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::camera
