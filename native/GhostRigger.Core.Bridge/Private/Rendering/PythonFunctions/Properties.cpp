#include "Rendering/PythonFunctions/Properties.h"

namespace ghostrigger::core::bridge::rendering {

const NativeFunctionImplementation& gpurenderer_is_gpu_line_2716_996d44b7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Bridge",
        "ghostrigger::core::bridge::rendering::moderngl_renderer_impl",
        "src/adapters/rendering/moderngl_renderer_impl.py",
        "GpuRenderer.is_gpu",
        "properties",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Bridge","namespace":"ghostrigger::core::bridge::rendering::moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer.is_gpu","name":"is_gpu","callable_type":"properties","line":2716,"end_line":2718,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fallbackviewportrenderer_name_line_127_fde2575f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Bridge",
        "ghostrigger::core::bridge::rendering::renderer_factory",
        "src/adapters/rendering/renderer_factory.py",
        "FallbackViewportRenderer.name",
        "properties",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Bridge","namespace":"ghostrigger::core::bridge::rendering::renderer_factory","python_file":"src/adapters/rendering/renderer_factory.py","qualname":"FallbackViewportRenderer.name","name":"name","callable_type":"properties","line":127,"end_line":129,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fallbackviewportrenderer_backend_id_line_132_2bc3f975_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Bridge",
        "ghostrigger::core::bridge::rendering::renderer_factory",
        "src/adapters/rendering/renderer_factory.py",
        "FallbackViewportRenderer.backend_id",
        "properties",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Bridge","namespace":"ghostrigger::core::bridge::rendering::renderer_factory","python_file":"src/adapters/rendering/renderer_factory.py","qualname":"FallbackViewportRenderer.backend_id","name":"backend_id","callable_type":"properties","line":132,"end_line":137,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fallbackviewportrenderer_active_renderer_line_196_3eb56d6b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Bridge",
        "ghostrigger::core::bridge::rendering::renderer_factory",
        "src/adapters/rendering/renderer_factory.py",
        "FallbackViewportRenderer.active_renderer",
        "properties",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Bridge","namespace":"ghostrigger::core::bridge::rendering::renderer_factory","python_file":"src/adapters/rendering/renderer_factory.py","qualname":"FallbackViewportRenderer.active_renderer","name":"active_renderer","callable_type":"properties","line":196,"end_line":197,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fallbackviewportrenderer_active_backend_line_200_710bb50c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Bridge",
        "ghostrigger::core::bridge::rendering::renderer_factory",
        "src/adapters/rendering/renderer_factory.py",
        "FallbackViewportRenderer.active_backend",
        "properties",
        "native_contract_complete",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Bridge","namespace":"ghostrigger::core::bridge::rendering::renderer_factory","python_file":"src/adapters/rendering/renderer_factory.py","qualname":"FallbackViewportRenderer.active_backend","name":"active_backend","callable_type":"properties","line":200,"end_line":201,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_complete","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":false})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gpurenderer_is_gpu_line_2716_996d44b7_native(),
        fallbackviewportrenderer_name_line_127_fde2575f_native(),
        fallbackviewportrenderer_backend_id_line_132_2bc3f975_native(),
        fallbackviewportrenderer_active_renderer_line_196_3eb56d6b_native(),
        fallbackviewportrenderer_active_backend_line_200_710bb50c_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::bridge::rendering

