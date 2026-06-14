#include "PythonFunctions/Properties.h"

namespace ghostrigger::domain::core::resources {

const NativeFunctionImplementation& gameresourcerecord_resref_line_116_3d616c56_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Resources",
        "ghostrigger::domain::core::resources::core::resources::game_resource_provider",
        "src/core/resources/game_resource_provider.py",
        "GameResourceRecord.resref",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Resources","namespace":"ghostrigger::domain::core::resources::core::resources::game_resource_provider","python_file":"src/core/resources/game_resource_provider.py","qualname":"GameResourceRecord.resref","name":"resref","callable_type":"properties","line":116,"end_line":117,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gameresourcerecord_restype_line_120_1d46f82f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Resources",
        "ghostrigger::domain::core::resources::core::resources::game_resource_provider",
        "src/core/resources/game_resource_provider.py",
        "GameResourceRecord.restype",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Resources","namespace":"ghostrigger::domain::core::resources::core::resources::game_resource_provider","python_file":"src/core/resources/game_resource_provider.py","qualname":"GameResourceRecord.restype","name":"restype","callable_type":"properties","line":120,"end_line":121,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gameresourcerecord_layer_line_124_3bab406c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Resources",
        "ghostrigger::domain::core::resources::core::resources::game_resource_provider",
        "src/core/resources/game_resource_provider.py",
        "GameResourceRecord.layer",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Resources","namespace":"ghostrigger::domain::core::resources::core::resources::game_resource_provider","python_file":"src/core/resources/game_resource_provider.py","qualname":"GameResourceRecord.layer","name":"layer","callable_type":"properties","line":124,"end_line":125,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gameresourcerecord_key_line_128_f409ca4e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Resources",
        "ghostrigger::domain::core::resources::core::resources::game_resource_provider",
        "src/core/resources/game_resource_provider.py",
        "GameResourceRecord.key",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Resources","namespace":"ghostrigger::domain::core::resources::core::resources::game_resource_provider","python_file":"src/core/resources/game_resource_provider.py","qualname":"GameResourceRecord.key","name":"key","callable_type":"properties","line":128,"end_line":134,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gameresourceresult_address_line_147_0e30bfb9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Resources",
        "ghostrigger::domain::core::resources::core::resources::game_resource_provider",
        "src/core/resources/game_resource_provider.py",
        "GameResourceResult.address",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Resources","namespace":"ghostrigger::domain::core::resources::core::resources::game_resource_provider","python_file":"src/core/resources/game_resource_provider.py","qualname":"GameResourceResult.address","name":"address","callable_type":"properties","line":147,"end_line":148,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gameresourcerecord_resref_line_116_3d616c56_native(),
        gameresourcerecord_restype_line_120_1d46f82f_native(),
        gameresourcerecord_layer_line_124_3bab406c_native(),
        gameresourcerecord_key_line_128_f409ca4e_native(),
        gameresourceresult_address_line_147_0e30bfb9_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::resources
