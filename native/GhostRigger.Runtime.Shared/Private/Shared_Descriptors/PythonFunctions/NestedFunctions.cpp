#include "Shared_Descriptors/PythonFunctions/NestedFunctions.h"

namespace ghostrigger::runtime::core::host::shared::descriptors {

const NativeFunctionImplementation& cached_world_position_resolver_world_transform_line_189_c0b42698_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared",
        "ghostrigger::runtime::core::host::shared::descriptors::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_cached_world_position_resolver.world_transform",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared","namespace":"ghostrigger::runtime::core::host::shared::descriptors::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_cached_world_position_resolver.world_transform","name":"world_transform","callable_type":"nested_functions","line":189,"end_line":215,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& cached_world_position_resolver_world_position_line_217_44c528c3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared",
        "ghostrigger::runtime::core::host::shared::descriptors::core::rendering::skeleton_render_data",
        "src/core/rendering/skeleton_render_data.py",
        "_cached_world_position_resolver.world_position",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared","namespace":"ghostrigger::runtime::core::host::shared::descriptors::core::rendering::skeleton_render_data","python_file":"src/core/rendering/skeleton_render_data.py","qualname":"_cached_world_position_resolver.world_position","name":"world_position","callable_type":"nested_functions","line":217,"end_line":218,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        cached_world_position_resolver_world_transform_line_189_c0b42698_native(),
        cached_world_position_resolver_world_position_line_217_44c528c3_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::runtime::core::host::shared::descriptors
