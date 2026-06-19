#include "PythonFunctions/Properties.h"

namespace ghostrigger::core::unreal {

const NativeFunctionImplementation& bonemappingreport_matched_count_line_115_46b24e61_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Unreal",
        "ghostrigger::core::unreal::animation_retargeting",
        "src/unreal/animation_retargeting.py",
        "BoneMappingReport.matched_count",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Unreal","namespace":"ghostrigger::core::unreal::animation_retargeting","python_file":"src/unreal/animation_retargeting.py","qualname":"BoneMappingReport.matched_count","name":"matched_count","callable_type":"properties","line":115,"end_line":116,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bonemappingreport_derived_count_line_119_fce392dc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Unreal",
        "ghostrigger::core::unreal::animation_retargeting",
        "src/unreal/animation_retargeting.py",
        "BoneMappingReport.derived_count",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Unreal","namespace":"ghostrigger::core::unreal::animation_retargeting","python_file":"src/unreal/animation_retargeting.py","qualname":"BoneMappingReport.derived_count","name":"derived_count","callable_type":"properties","line":119,"end_line":120,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& unrealskeletonasset_bone_count_line_48_9f2efdff_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Unreal",
        "ghostrigger::core::unreal::quinn",
        "src/unreal/quinn.py",
        "UnrealSkeletonAsset.bone_count",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Unreal","namespace":"ghostrigger::core::unreal::quinn","python_file":"src/unreal/quinn.py","qualname":"UnrealSkeletonAsset.bone_count","name":"bone_count","callable_type":"properties","line":48,"end_line":49,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        bonemappingreport_matched_count_line_115_46b24e61_native(),
        bonemappingreport_derived_count_line_119_fce392dc_native(),
        unrealskeletonasset_bone_count_line_48_9f2efdff_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::unreal
