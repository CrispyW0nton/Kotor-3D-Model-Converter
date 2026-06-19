#include "PythonFunctions/Properties.h"

namespace ghostrigger::graphics::renderer::backend::moderngl {

const NativeFunctionImplementation& gpurenderer_is_gpu_line_2716_996d44b7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Graphics.Renderer.Backend.ModernGL",
        "ghostrigger::graphics::renderer::backend::moderngl::adapters::rendering::moderngl_renderer_impl",
        "src/adapters/rendering/moderngl_renderer_impl.py",
        "GpuRenderer.is_gpu",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Graphics.Renderer.Backend.ModernGL","namespace":"ghostrigger::graphics::renderer::backend::moderngl::adapters::rendering::moderngl_renderer_impl","python_file":"src/adapters/rendering/moderngl_renderer_impl.py","qualname":"GpuRenderer.is_gpu","name":"is_gpu","callable_type":"properties","line":2716,"end_line":2718,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gpurenderer_is_gpu_line_2716_996d44b7_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::graphics::renderer::backend::moderngl
