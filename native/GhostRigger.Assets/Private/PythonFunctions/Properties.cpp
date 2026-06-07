#include "PythonFunctions/Properties.h"

namespace ghostrigger::assets {

const NativeFunctionImplementation& overridelayer_game_dir_line_112_49db4eaa_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Assets",
        "ghostrigger::assets::core::assets::override_layer",
        "src/core/assets/override_layer.py",
        "OverrideLayer.game_dir",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Assets","namespace":"ghostrigger::assets::core::assets::override_layer","python_file":"src/core/assets/override_layer.py","qualname":"OverrideLayer.game_dir","name":"game_dir","callable_type":"properties","line":112,"end_line":113,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& overridelayer_override_dir_line_116_d702c23f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Assets",
        "ghostrigger::assets::core::assets::override_layer",
        "src/core/assets/override_layer.py",
        "OverrideLayer.override_dir",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Assets","namespace":"ghostrigger::assets::core::assets::override_layer","python_file":"src/core/assets/override_layer.py","qualname":"OverrideLayer.override_dir","name":"override_dir","callable_type":"properties","line":116,"end_line":117,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& overridelayer_is_available_line_120_4fde95ac_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Assets",
        "ghostrigger::assets::core::assets::override_layer",
        "src/core/assets/override_layer.py",
        "OverrideLayer.is_available",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Assets","namespace":"ghostrigger::assets::core::assets::override_layer","python_file":"src/core/assets/override_layer.py","qualname":"OverrideLayer.is_available","name":"is_available","callable_type":"properties","line":120,"end_line":122,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& overridelayer_entry_count_line_125_b6182ba0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Assets",
        "ghostrigger::assets::core::assets::override_layer",
        "src/core/assets/override_layer.py",
        "OverrideLayer.entry_count",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Assets","namespace":"ghostrigger::assets::core::assets::override_layer","python_file":"src/core/assets/override_layer.py","qualname":"OverrideLayer.entry_count","name":"entry_count","callable_type":"properties","line":125,"end_line":127,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        overridelayer_game_dir_line_112_49db4eaa_native(),
        overridelayer_override_dir_line_116_d702c23f_native(),
        overridelayer_is_available_line_120_4fde95ac_native(),
        overridelayer_entry_count_line_125_b6182ba0_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::assets
