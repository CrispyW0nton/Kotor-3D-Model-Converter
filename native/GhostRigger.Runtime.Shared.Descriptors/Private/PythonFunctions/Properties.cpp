#include "PythonFunctions/Properties.h"

namespace ghostrigger::runtime::shared::descriptors {

const NativeFunctionImplementation& pivotdata_position_line_54_fa472186_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared.Descriptors",
        "ghostrigger::runtime::shared::descriptors::core::scene::scene_object",
        "src/core/scene/scene_object.py",
        "PivotData.position",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared.Descriptors","namespace":"ghostrigger::runtime::shared::descriptors::core::scene::scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.position","name":"position","callable_type":"properties","line":54,"end_line":55,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& pivotdata_rotation_line_62_8f4a7cea_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared.Descriptors",
        "ghostrigger::runtime::shared::descriptors::core::scene::scene_object",
        "src/core/scene/scene_object.py",
        "PivotData.rotation",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared.Descriptors","namespace":"ghostrigger::runtime::shared::descriptors::core::scene::scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.rotation","name":"rotation","callable_type":"properties","line":62,"end_line":63,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        pivotdata_position_line_54_fa472186_native(),
        pivotdata_rotation_line_62_8f4a7cea_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::runtime::shared::descriptors
