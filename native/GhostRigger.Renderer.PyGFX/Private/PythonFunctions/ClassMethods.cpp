#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::renderer::pygfx {

const NativeFunctionImplementation& pygfxviewportrenderer_probe_availability_line_87_bda39575_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Renderer.PyGFX",
        "ghostrigger::renderer::pygfx::adapters::rendering::pygfx_core::renderer",
        "src/adapters/rendering/pygfx_core/renderer.py",
        "PygfxViewportRenderer.probe_availability",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Renderer.PyGFX","namespace":"ghostrigger::renderer::pygfx::adapters::rendering::pygfx_core::renderer","python_file":"src/adapters/rendering/pygfx_core/renderer.py","qualname":"PygfxViewportRenderer.probe_availability","name":"probe_availability","callable_type":"class_methods","line":87,"end_line":125,"signature":{"args":["cls"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& pygfxscenebridge_polyline_to_segments_line_524_5d05e78c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Renderer.PyGFX",
        "ghostrigger::renderer::pygfx::adapters::rendering::pygfx_core::scene_bridge",
        "src/adapters/rendering/pygfx_core/scene_bridge.py",
        "PygfxSceneBridge._polyline_to_segments",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Renderer.PyGFX","namespace":"ghostrigger::renderer::pygfx::adapters::rendering::pygfx_core::scene_bridge","python_file":"src/adapters/rendering/pygfx_core/scene_bridge.py","qualname":"PygfxSceneBridge._polyline_to_segments","name":"_polyline_to_segments","callable_type":"class_methods","line":524,"end_line":531,"signature":{"args":["cls","points"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        pygfxviewportrenderer_probe_availability_line_87_bda39575_native(),
        pygfxscenebridge_polyline_to_segments_line_524_5d05e78c_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::renderer::pygfx
