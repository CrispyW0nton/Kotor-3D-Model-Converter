#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::domain::core::validation {

const NativeFunctionImplementation& validate_raw_animation_footprint_walk_line_148_d39479ce_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Validation",
        "ghostrigger::domain::core::validation::core::validation::animation_block_validator",
        "src/core/validation/animation_block_validator.py",
        "validate_raw_animation_footprint.walk",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Validation","namespace":"ghostrigger::domain::core::validation::core::validation::animation_block_validator","python_file":"src/core/validation/animation_block_validator.py","qualname":"validate_raw_animation_footprint.walk","name":"walk","callable_type":"nested_functions","line":148,"end_line":228,"signature":{"args":["node_rel"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& validationbus_subscribe_unsubscribe_line_158_b8f03986_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Validation",
        "ghostrigger::domain::core::validation::core::validation::validation_bus",
        "src/core/validation/validation_bus.py",
        "ValidationBus.subscribe.unsubscribe",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Validation","namespace":"ghostrigger::domain::core::validation::core::validation::validation_bus","python_file":"src/core/validation/validation_bus.py","qualname":"ValidationBus.subscribe.unsubscribe","name":"unsubscribe","callable_type":"nested_functions","line":158,"end_line":162,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        validate_raw_animation_footprint_walk_line_148_d39479ce_native(),
        validationbus_subscribe_unsubscribe_line_158_b8f03986_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::validation
