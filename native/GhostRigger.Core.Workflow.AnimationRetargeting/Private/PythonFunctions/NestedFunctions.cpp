#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::animationretargeting {

const NativeFunctionImplementation& world_positions_by_key_visit_line_201_388300ca_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Workflow.AnimationRetargeting",
        "ghostrigger::core::animationretargeting::core::animation_retargeting::retargeter",
        "src/core/animation_retargeting/retargeter.py",
        "_world_positions_by_key.visit",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Workflow.AnimationRetargeting","namespace":"ghostrigger::core::animationretargeting::core::animation_retargeting::retargeter","python_file":"src/core/animation_retargeting/retargeter.py","qualname":"_world_positions_by_key.visit","name":"visit","callable_type":"nested_functions","line":201,"end_line":208,"signature":{"args":["node","parent_pos"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        world_positions_by_key_visit_line_201_388300ca_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::animationretargeting
