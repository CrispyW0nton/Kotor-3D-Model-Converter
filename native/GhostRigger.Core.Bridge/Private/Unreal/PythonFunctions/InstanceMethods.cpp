#include "Unreal/PythonFunctions/InstanceMethods.h"

namespace ghostrigger::core::unreal {

const NativeFunctionImplementation& fbxnode_child_line_58_e1028af9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Bridge.vcxproj",
        "ghostrigger::core::unreal::quinn",
        "src/unreal/quinn.py",
        "_FbxNode.child",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Bridge.vcxproj","namespace":"ghostrigger::core::unreal::quinn","python_file":"src/unreal/quinn.py","qualname":"_FbxNode.child","name":"child","callable_type":"instance_methods","line":58,"end_line":62,"signature":{"args":["self","name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fbxnode_children_named_line_64_07b0592d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Bridge.vcxproj",
        "ghostrigger::core::unreal::quinn",
        "src/unreal/quinn.py",
        "_FbxNode.children_named",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Bridge.vcxproj","namespace":"ghostrigger::core::unreal::quinn","python_file":"src/unreal/quinn.py","qualname":"_FbxNode.children_named","name":"children_named","callable_type":"instance_methods","line":64,"end_line":65,"signature":{"args":["self","name"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        fbxnode_child_line_58_e1028af9_native(),
        fbxnode_children_named_line_64_07b0592d_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::unreal
