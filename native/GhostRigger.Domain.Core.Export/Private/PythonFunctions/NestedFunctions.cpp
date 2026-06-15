#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::domain::core::export_ {

const NativeFunctionImplementation& gltfimporter_process_pygltflib_acc_line_518_3d5ae96e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Export",
        "ghostrigger::domain::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "GLTFImporter._process_pygltflib._acc",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Export","namespace":"ghostrigger::domain::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"GLTFImporter._process_pygltflib._acc","name":"_acc","callable_type":"nested_functions","line":518,"end_line":542,"signature":{"args":["idx"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gltfimporter_import_builtin_bytes_acc_line_726_d6c230cd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Export",
        "ghostrigger::domain::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "GLTFImporter._import_builtin_bytes._acc",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Export","namespace":"ghostrigger::domain::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"GLTFImporter._import_builtin_bytes._acc","name":"_acc","callable_type":"nested_functions","line":726,"end_line":727,"signature":{"args":["idx"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& candidate_blender_executables_add_line_1087_320d6829_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Export",
        "ghostrigger::domain::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_candidate_blender_executables.add",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Export","namespace":"ghostrigger::domain::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_candidate_blender_executables.add","name":"add","callable_type":"nested_functions","line":1087,"end_line":1096,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gltfimporter_process_pygltflib_acc_line_518_3d5ae96e_native(),
        gltfimporter_import_builtin_bytes_acc_line_726_d6c230cd_native(),
        candidate_blender_executables_add_line_1087_320d6829_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::export_
