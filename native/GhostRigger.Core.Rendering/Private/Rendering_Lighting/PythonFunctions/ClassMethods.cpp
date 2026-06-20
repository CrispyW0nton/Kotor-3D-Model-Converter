#include "Rendering_Lighting/PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::lighting {

const NativeFunctionImplementation& ghostriggerlight_from_object_line_60_d4b090e4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::lighting::core::lighting::light_model",
        "src/core/lighting/light_model.py",
        "GhostRiggerLight.from_object",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::lighting::core::lighting::light_model","python_file":"src/core/lighting/light_model.py","qualname":"GhostRiggerLight.from_object","name":"from_object","callable_type":"class_methods","line":60,"end_line":91,"signature":{"args":["cls","obj","source_type"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lightmapbakesettings_for_quality_line_123_5a1517f1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::lighting::core::lighting::lightmap_bake_settings",
        "src/core/lighting/lightmap_bake_settings.py",
        "LightmapBakeSettings.for_quality",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::lighting::core::lighting::lightmap_bake_settings","python_file":"src/core/lighting/lightmap_bake_settings.py","qualname":"LightmapBakeSettings.for_quality","name":"for_quality","callable_type":"class_methods","line":123,"end_line":162,"signature":{"args":["cls","preset"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":true},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& emitterconfig_from_node_line_218_43df53e1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering",
        "ghostrigger::core::lighting::core::lighting::particle_emitter",
        "src/core/lighting/particle_emitter.py",
        "EmitterConfig.from_node",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering","namespace":"ghostrigger::core::lighting::core::lighting::particle_emitter","python_file":"src/core/lighting/particle_emitter.py","qualname":"EmitterConfig.from_node","name":"from_node","callable_type":"class_methods","line":218,"end_line":255,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        ghostriggerlight_from_object_line_60_d4b090e4_native(),
        lightmapbakesettings_for_quality_line_123_5a1517f1_native(),
        emitterconfig_from_node_line_218_43df53e1_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::lighting
