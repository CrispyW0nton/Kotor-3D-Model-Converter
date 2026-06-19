#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::camera {

const NativeFunctionImplementation& ghostriggercamera_from_object_line_63_00a75f63_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Camera",
        "ghostrigger::core::camera::core::camera::camera_model",
        "src/core/camera/camera_model.py",
        "GhostRiggerCamera.from_object",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Camera","namespace":"ghostrigger::core::camera::core::camera::camera_model","python_file":"src/core/camera/camera_model.py","qualname":"GhostRiggerCamera.from_object","name":"from_object","callable_type":"class_methods","line":63,"end_line":80,"signature":{"args":["cls","obj"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& ghostriggercamera_from_dict_line_83_1d2e8091_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Camera",
        "ghostrigger::core::camera::core::camera::camera_model",
        "src/core/camera/camera_model.py",
        "GhostRiggerCamera.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Camera","namespace":"ghostrigger::core::camera::core::camera::camera_model","python_file":"src/core/camera/camera_model.py","qualname":"GhostRiggerCamera.from_dict","name":"from_dict","callable_type":"class_methods","line":83,"end_line":97,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rendersettings_from_dict_line_41_2f47dc1e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Camera",
        "ghostrigger::core::camera::core::camera::camera_render_settings",
        "src/core/camera/camera_render_settings.py",
        "RenderSettings.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Camera","namespace":"ghostrigger::core::camera::core::camera::camera_render_settings","python_file":"src/core/camera/camera_render_settings.py","qualname":"RenderSettings.from_dict","name":"from_dict","callable_type":"class_methods","line":41,"end_line":45,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        ghostriggercamera_from_object_line_63_00a75f63_native(),
        ghostriggercamera_from_dict_line_83_1d2e8091_native(),
        rendersettings_from_dict_line_41_2f47dc1e_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::camera
