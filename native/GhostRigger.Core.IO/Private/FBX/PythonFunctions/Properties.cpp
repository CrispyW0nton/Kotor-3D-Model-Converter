#include "FBX/PythonFunctions/Properties.h"

namespace ghostrigger::core::io {

const NativeFunctionImplementation& fbxsdkmodules_available_line_22_df5f76b9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.IO",
        "ghostrigger::core::io::fbx::fbx_sdk_loader",
        "src/io/fbx/fbx_sdk_loader.py",
        "FbxSdkModules.available",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.IO","namespace":"ghostrigger::core::io::fbx::fbx_sdk_loader","python_file":"src/io/fbx/fbx_sdk_loader.py","qualname":"FbxSdkModules.available","name":"available","callable_type":"properties","line":22,"end_line":23,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        fbxsdkmodules_available_line_22_df5f76b9_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::io
