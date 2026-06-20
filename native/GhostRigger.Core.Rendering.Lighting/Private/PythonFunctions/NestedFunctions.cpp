#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::lighting {

const NativeFunctionImplementation& lightmanager_make_light_node_all_nodes_with_generated_line_186_39c41903_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Lighting",
        "ghostrigger::core::lighting::core::lighting::light_manager",
        "src/core/lighting/light_manager.py",
        "LightManager._make_light_node._all_nodes_with_generated",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Lighting","namespace":"ghostrigger::core::lighting::core::lighting::light_manager","python_file":"src/core/lighting/light_manager.py","qualname":"LightManager._make_light_node._all_nodes_with_generated","name":"_all_nodes_with_generated","callable_type":"nested_functions","line":186,"end_line":187,"signature":{"args":["_orig","_model"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        lightmanager_make_light_node_all_nodes_with_generated_line_186_39c41903_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::lighting
