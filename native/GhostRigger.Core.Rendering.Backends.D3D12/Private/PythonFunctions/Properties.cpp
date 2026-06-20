#include "PythonFunctions/Properties.h"

namespace ghostrigger::core::rendering::backends::d3d12 {

const NativeFunctionImplementation& compositemodel_nodes_line_292_c770f0f1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Backends.D3D12",
        "ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_scene_helpers",
        "src/core/rendering/gpu_scene_helpers.py",
        "_CompositeModel.nodes",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Backends.D3D12","namespace":"ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_scene_helpers","python_file":"src/core/rendering/gpu_scene_helpers.py","qualname":"_CompositeModel.nodes","name":"nodes","callable_type":"properties","line":292,"end_line":293,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        compositemodel_nodes_line_292_c770f0f1_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::rendering::backends::d3d12
