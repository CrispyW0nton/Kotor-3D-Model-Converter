#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::unreal {

const NativeFunctionImplementation& world_positions_by_key_visit_line_343_1fe69925_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.Unreal",
        "ghostrigger::core::unreal::animation_retargeting",
        "src/unreal/animation_retargeting.py",
        "_world_positions_by_key.visit",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.Unreal","namespace":"ghostrigger::core::unreal::animation_retargeting","python_file":"src/unreal/animation_retargeting.py","qualname":"_world_positions_by_key.visit","name":"visit","callable_type":"nested_functions","line":343,"end_line":350,"signature":{"args":["node","parent_pos"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        world_positions_by_key_visit_line_343_1fe69925_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::unreal
