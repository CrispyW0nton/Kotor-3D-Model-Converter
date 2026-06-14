#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::tools::workflow::export_ {

const NativeFunctionImplementation& glbreader_from_file_line_140_8725bc1b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.Export",
        "ghostrigger::tools::workflow::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "GLBReader.from_file",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.Export","namespace":"ghostrigger::tools::workflow::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"GLBReader.from_file","name":"from_file","callable_type":"class_methods","line":140,"end_line":141,"signature":{"args":["cls","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& glbreader_from_bytes_line_144_89250c96_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.Workflow.Export",
        "ghostrigger::tools::workflow::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "GLBReader.from_bytes",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.Workflow.Export","namespace":"ghostrigger::tools::workflow::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"GLBReader.from_bytes","name":"from_bytes","callable_type":"class_methods","line":144,"end_line":145,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        glbreader_from_file_line_140_8725bc1b_native(),
        glbreader_from_bytes_line_144_89250c96_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::workflow::export_
