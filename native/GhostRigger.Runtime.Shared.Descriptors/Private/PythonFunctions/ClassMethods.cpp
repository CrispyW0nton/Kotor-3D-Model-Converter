#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::runtime::core::host::shared::descriptors {

const NativeFunctionImplementation& resourceaddress_from_dict_line_87_734cf9ce_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared.Descriptors",
        "ghostrigger::runtime::core::host::shared::descriptors::core::project::resource_address",
        "src/core/project/resource_address.py",
        "ResourceAddress.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared.Descriptors","namespace":"ghostrigger::runtime::core::host::shared::descriptors::core::project::resource_address","python_file":"src/core/project/resource_address.py","qualname":"ResourceAddress.from_dict","name":"from_dict","callable_type":"class_methods","line":87,"end_line":103,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& transform_from_dict_line_35_68aeedb9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared.Descriptors",
        "ghostrigger::runtime::core::host::shared::descriptors::core::scene::scene_object",
        "src/core/scene/scene_object.py",
        "Transform.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared.Descriptors","namespace":"ghostrigger::runtime::core::host::shared::descriptors::core::scene::scene_object","python_file":"src/core/scene/scene_object.py","qualname":"Transform.from_dict","name":"from_dict","callable_type":"class_methods","line":35,"end_line":41,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& pivotdata_from_dict_line_88_6fd6a9f3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared.Descriptors",
        "ghostrigger::runtime::core::host::shared::descriptors::core::scene::scene_object",
        "src/core/scene/scene_object.py",
        "PivotData.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared.Descriptors","namespace":"ghostrigger::runtime::core::host::shared::descriptors::core::scene::scene_object","python_file":"src/core/scene/scene_object.py","qualname":"PivotData.from_dict","name":"from_dict","callable_type":"class_methods","line":88,"end_line":102,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& sceneobjectinstance_from_dict_line_49_531c3383_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Runtime.Shared.Descriptors",
        "ghostrigger::runtime::core::host::shared::descriptors::core::scene::scene_object_instance",
        "src/core/scene/scene_object_instance.py",
        "SceneObjectInstance.from_dict",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Runtime.Shared.Descriptors","namespace":"ghostrigger::runtime::core::host::shared::descriptors::core::scene::scene_object_instance","python_file":"src/core/scene/scene_object_instance.py","qualname":"SceneObjectInstance.from_dict","name":"from_dict","callable_type":"class_methods","line":49,"end_line":63,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        resourceaddress_from_dict_line_87_734cf9ce_native(),
        transform_from_dict_line_35_68aeedb9_native(),
        pivotdata_from_dict_line_88_6fd6a9f3_native(),
        sceneobjectinstance_from_dict_line_49_531c3383_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::runtime::core::host::shared::descriptors
