#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::lighting {

const NativeFunctionImplementation& auroralightadapter_is_aurora_light_line_32_72871b3e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Lighting",
        "ghostrigger::core::lighting::core::lighting::aurora_light_adapter",
        "src/core/lighting/aurora_light_adapter.py",
        "AuroraLightAdapter.is_aurora_light",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Lighting","namespace":"ghostrigger::core::lighting::core::lighting::aurora_light_adapter","python_file":"src/core/lighting/aurora_light_adapter.py","qualname":"AuroraLightAdapter.is_aurora_light","name":"is_aurora_light","callable_type":"static_methods","line":32,"end_line":35,"signature":{"args":["record"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightingrigpresets_create_line_10_24da2ddb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Lighting",
        "ghostrigger::core::lighting::core::lighting::lighting_rig_presets",
        "src/core/lighting/lighting_rig_presets.py",
        "LightingRigPresets.create",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Lighting","namespace":"ghostrigger::core::lighting::core::lighting::lighting_rig_presets","python_file":"src/core/lighting/lighting_rig_presets.py","qualname":"LightingRigPresets.create","name":"create","callable_type":"static_methods","line":10,"end_line":67,"signature":{"args":["preset"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        auroralightadapter_is_aurora_light_line_32_72871b3e_native(),
        lightingrigpresets_create_line_10_24da2ddb_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::lighting
