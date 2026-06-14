#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::domain::core::validation {

const NativeFunctionImplementation& viewportvalidator_looks_like_ascii_mdl_line_58_29f4113d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Validation",
        "ghostrigger::domain::core::validation::core::validation::viewport_validator",
        "src/core/validation/viewport_validator.py",
        "ViewportValidator._looks_like_ascii_mdl",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Validation","namespace":"ghostrigger::domain::core::validation::core::validation::viewport_validator","python_file":"src/core/validation/viewport_validator.py","qualname":"ViewportValidator._looks_like_ascii_mdl","name":"_looks_like_ascii_mdl","callable_type":"static_methods","line":58,"end_line":69,"signature":{"args":["raw"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& viewportvalidator_game_version_line_72_8a0a958f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Validation",
        "ghostrigger::domain::core::validation::core::validation::viewport_validator",
        "src/core/validation/viewport_validator.py",
        "ViewportValidator._game_version",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Validation","namespace":"ghostrigger::domain::core::validation::core::validation::viewport_validator","python_file":"src/core/validation/viewport_validator.py","qualname":"ViewportValidator._game_version","name":"_game_version","callable_type":"static_methods","line":72,"end_line":75,"signature":{"args":["game"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& viewportvalidator_to_wxyz_line_245_84c4d9fa_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Validation",
        "ghostrigger::domain::core::validation::core::validation::viewport_validator",
        "src/core/validation/viewport_validator.py",
        "ViewportValidator._to_wxyz",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Validation","namespace":"ghostrigger::domain::core::validation::core::validation::viewport_validator","python_file":"src/core/validation/viewport_validator.py","qualname":"ViewportValidator._to_wxyz","name":"_to_wxyz","callable_type":"static_methods","line":245,"end_line":253,"signature":{"args":["rotation_xyzw"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& viewportvalidator_read_grayscale_line_283_29fcf5e8_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Validation",
        "ghostrigger::domain::core::validation::core::validation::viewport_validator",
        "src/core/validation/viewport_validator.py",
        "ViewportValidator._read_grayscale",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Validation","namespace":"ghostrigger::domain::core::validation::core::validation::viewport_validator","python_file":"src/core/validation/viewport_validator.py","qualname":"ViewportValidator._read_grayscale","name":"_read_grayscale","callable_type":"static_methods","line":283,"end_line":292,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        viewportvalidator_looks_like_ascii_mdl_line_58_29f4113d_native(),
        viewportvalidator_game_version_line_72_8a0a958f_native(),
        viewportvalidator_to_wxyz_line_245_84c4d9fa_native(),
        viewportvalidator_read_grayscale_line_283_29fcf5e8_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::validation
