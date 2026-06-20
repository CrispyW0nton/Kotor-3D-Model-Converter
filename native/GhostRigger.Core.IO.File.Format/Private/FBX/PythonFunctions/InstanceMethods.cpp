#include "FBX/PythonFunctions/InstanceMethods.h"

namespace ghostrigger::core::io {

const NativeFunctionImplementation& fbximportsummary_log_line_line_23_d3f43f45_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.IO.File.Format",
        "ghostrigger::core::io::fbx::fbx_scene_adapter",
        "src/io/fbx/fbx_scene_adapter.py",
        "FbxImportSummary.log_line",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.IO.File.Format","namespace":"ghostrigger::core::io::fbx::fbx_scene_adapter","python_file":"src/io/fbx/fbx_scene_adapter.py","qualname":"FbxImportSummary.log_line","name":"log_line","callable_type":"instance_methods","line":23,"end_line":27,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fbxexportsummary_log_line_line_39_848f749e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.IO.File.Format",
        "ghostrigger::core::io::fbx::fbx_scene_adapter",
        "src/io/fbx/fbx_scene_adapter.py",
        "FbxExportSummary.log_line",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.IO.File.Format","namespace":"ghostrigger::core::io::fbx::fbx_scene_adapter","python_file":"src/io/fbx/fbx_scene_adapter.py","qualname":"FbxExportSummary.log_line","name":"log_line","callable_type":"instance_methods","line":39,"end_line":43,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        fbximportsummary_log_line_line_23_d3f43f45_native(),
        fbxexportsummary_log_line_line_39_848f749e_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::io
