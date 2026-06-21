#include "Rendering_Backends_ModernGL/PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::rendering::backends::moderngl {

const NativeFunctionImplementation& gpurenderer_is_sprite_hilt_line_2650_5adc72a0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::backends::moderngl::adapters::rendering::moderngl_renderer_impl",
        "src/adapters/rendering/moderngl_renderer_impl.py",
        "GpuRenderer._is_sprite_hilt",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::backends::moderngl::adapters::rendering::moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer._is_sprite_hilt","name":"_is_sprite_hilt","callable_type":"class_methods","line":2650,"end_line":2662,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gpurenderer_sprite_alpha_source_line_2665_2b8129c9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::backends::moderngl::adapters::rendering::moderngl_renderer_impl",
        "src/adapters/rendering/moderngl_renderer_impl.py",
        "GpuRenderer._sprite_alpha_source",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::backends::moderngl::adapters::rendering::moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer._sprite_alpha_source","name":"_sprite_alpha_source","callable_type":"class_methods","line":2665,"end_line":2674,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gpurenderer_sprite_glow_line_2677_fe0a0901_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::rendering::backends::moderngl::adapters::rendering::moderngl_renderer_impl",
        "src/adapters/rendering/moderngl_renderer_impl.py",
        "GpuRenderer._sprite_glow",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::rendering::backends::moderngl::adapters::rendering::moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer._sprite_glow","name":"_sprite_glow","callable_type":"class_methods","line":2677,"end_line":2687,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gpurenderer_is_sprite_hilt_line_2650_5adc72a0_native(),
        gpurenderer_sprite_alpha_source_line_2665_2b8129c9_native(),
        gpurenderer_sprite_glow_line_2677_fe0a0901_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::rendering::backends::moderngl
