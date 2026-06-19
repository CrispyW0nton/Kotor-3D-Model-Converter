#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::core::export_ {

const NativeFunctionImplementation& run_export_job_line_108_e68b41e9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "run_export_job",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"run_export_job","name":"run_export_job","callable_type":"module_functions","line":108,"end_line":260,"signature":{"args":["request","writer","verifier","manifest_writer","validation_bus"],"positional_count":1,"keyword_only_count":4,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& preflight_export_request_line_263_01b4bba5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_preflight_export_request",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_preflight_export_request","name":"_preflight_export_request","callable_type":"module_functions","line":263,"end_line":316,"signature":{"args":["request"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& validate_staged_outputs_line_319_8e66a640_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_validate_staged_outputs",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_validate_staged_outputs","name":"_validate_staged_outputs","callable_type":"module_functions","line":319,"end_line":331,"signature":{"args":["context"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& result_line_334_e9ef6bd5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_result",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_result","name":"_result","callable_type":"module_functions","line":334,"end_line":359,"signature":{"args":["request","status","report","staged_paths","final_paths","manifest_path"],"positional_count":3,"keyword_only_count":3,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& single_issue_report_line_362_5757b4ff_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_single_issue_report",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_single_issue_report","name":"_single_issue_report","callable_type":"module_functions","line":362,"end_line":382,"signature":{"args":["request","code","message","severity","details"],"positional_count":1,"keyword_only_count":4,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& issue_line_385_4db8c74f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_issue",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_issue","name":"_issue","callable_type":"module_functions","line":385,"end_line":398,"signature":{"args":["code","message","severity","details"],"positional_count":2,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& publish_line_401_a53a92e7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_publish",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_publish","name":"_publish","callable_type":"module_functions","line":401,"end_line":410,"signature":{"args":["validation_bus","request","report"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& shared_output_parent_line_413_001c658b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_shared_output_parent",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_shared_output_parent","name":"_shared_output_parent","callable_type":"module_functions","line":413,"end_line":419,"signature":{"args":["outputs"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& rollback_promoted_outputs_line_422_6cf28be4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_rollback_promoted_outputs",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_rollback_promoted_outputs","name":"_rollback_promoted_outputs","callable_type":"module_functions","line":422,"end_line":436,"signature":{"args":["final_paths","backups"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& final_manifest_path_line_439_188f8463_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_final_manifest_path",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_final_manifest_path","name":"_final_manifest_path","callable_type":"module_functions","line":439,"end_line":443,"signature":{"args":["request","staged_manifest"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalized_path_key_line_446_7fbdeaec_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_normalized_path_key",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_normalized_path_key","name":"_normalized_path_key","callable_type":"module_functions","line":446,"end_line":447,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& safe_job_id_line_450_e73ab220_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_safe_job_id",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_safe_job_id","name":"_safe_job_id","callable_type":"module_functions","line":450,"end_line":452,"signature":{"args":["job_id"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& ensure_json_serializable_line_455_dc882db9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "_ensure_json_serializable",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"_ensure_json_serializable","name":"_ensure_json_serializable","callable_type":"module_functions","line":455,"end_line":459,"signature":{"args":["value","context"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& decode_accessor_line_152_6f438c5e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_decode_accessor",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_decode_accessor","name":"_decode_accessor","callable_type":"module_functions","line":152,"end_line":224,"signature":{"args":["gltf_dict","buffers","acc_idx"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& resolve_buffers_line_231_3b6565af_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_resolve_buffers",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_resolve_buffers","name":"_resolve_buffers","callable_type":"module_functions","line":231,"end_line":262,"signature":{"args":["gltf_dict","base_dir","bin_chunk"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& matrix_to_trs_line_265_79964a2c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_matrix_to_trs",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_matrix_to_trs","name":"_matrix_to_trs","callable_type":"module_functions","line":265,"end_line":315,"signature":{"args":["matrix"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_trs_from_mapping_line_318_b07a17f5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_node_trs_from_mapping",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_node_trs_from_mapping","name":"_node_trs_from_mapping","callable_type":"module_functions","line":318,"end_line":330,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_scale_from_mapping_line_333_5454ffdb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_node_scale_from_mapping",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_node_scale_from_mapping","name":"_node_scale_from_mapping","callable_type":"module_functions","line":333,"end_line":343,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_trs_from_object_line_346_bdd95aaa_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_node_trs_from_object",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_node_trs_from_object","name":"_node_trs_from_object","callable_type":"module_functions","line":346,"end_line":358,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& node_scale_from_object_line_361_ddbf387c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_node_scale_from_object",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_node_scale_from_object","name":"_node_scale_from_object","callable_type":"module_functions","line":361,"end_line":366,"signature":{"args":["node"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& mul_scale_line_369_72dca566_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_mul_scale",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_mul_scale","name":"_mul_scale","callable_type":"module_functions","line":369,"end_line":373,"signature":{"args":["a","b"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& apply_scale_to_pos_line_376_1219d937_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_apply_scale_to_pos",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_apply_scale_to_pos","name":"_apply_scale_to_pos","callable_type":"module_functions","line":376,"end_line":380,"signature":{"args":["pos","scale"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& compose_gltf_world_line_383_c0f9e7e1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_compose_gltf_world",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_compose_gltf_world","name":"_compose_gltf_world","callable_type":"module_functions","line":383,"end_line":397,"signature":{"args":["local_pos","local_rot","parent_world","parent_rot","parent_scale"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& gltf_root_indices_line_400_1b3f99ac_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_gltf_root_indices",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_gltf_root_indices","name":"_gltf_root_indices","callable_type":"module_functions","line":400,"end_line":420,"signature":{"args":["nodes","scenes","scene_idx"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& candidate_blender_executables_line_1082_aaa33477_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_candidate_blender_executables",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_candidate_blender_executables","name":"_candidate_blender_executables","callable_type":"module_functions","line":1082,"end_line":1122,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& blender_sort_key_line_1125_18a02b8a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_blender_sort_key",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_blender_sort_key","name":"_blender_sort_key","callable_type":"module_functions","line":1125,"end_line":1133,"signature":{"args":["path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& convert_fbx_to_glb_with_blender_line_1136_428ff1fd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_convert_fbx_to_glb_with_blender",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_convert_fbx_to_glb_with_blender","name":"_convert_fbx_to_glb_with_blender","callable_type":"module_functions","line":1136,"end_line":1177,"signature":{"args":["blender_exe","fbx_path","glb_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& auto_import_line_1184_b404afc0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "auto_import",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"auto_import","name":"auto_import","callable_type":"module_functions","line":1184,"end_line":1208,"signature":{"args":["path","model_name","game_version","supermodel","classification"],"positional_count":5,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& build_skin_data_line_1215_fcd8f9f0_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_build_skin_data",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_build_skin_data","name":"_build_skin_data","callable_type":"module_functions","line":1215,"end_line":1235,"signature":{"args":["joints_data","weights_data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& channel_to_controller_line_1238_6e25f4a7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_channel_to_controller",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_channel_to_controller","name":"_channel_to_controller","callable_type":"module_functions","line":1238,"end_line":1255,"signature":{"args":["path","values_raw"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& fill_material_pygltflib_line_1258_6367fccf_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::gltf_importer",
        "src/core/export/gltf_importer.py",
        "_fill_material_pygltflib",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::gltf_importer","python_file":"src/core/export/gltf_importer.py","qualname":"_fill_material_pygltflib","name":"_fill_material_pygltflib","callable_type":"module_functions","line":1258,"end_line":1286,"signature":{"args":["gltf","prim","mnode"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& asset_relative_line_18_5ce50433_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_export_bridge",
        "src/core/export/unity_export_bridge.py",
        "asset_relative",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_export_bridge","python_file":"src/core/export/unity_export_bridge.py","qualname":"asset_relative","name":"asset_relative","callable_type":"module_functions","line":18,"end_line":24,"signature":{"args":["path","unity_project"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& build_output_paths_line_27_18384c92_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_export_bridge",
        "src/core/export/unity_export_bridge.py",
        "build_output_paths",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_export_bridge","python_file":"src/core/export/unity_export_bridge.py","qualname":"build_output_paths","name":"build_output_paths","callable_type":"module_functions","line":27,"end_line":38,"signature":{"args":["unity_project","asset_subdir","resref","extension"],"positional_count":4,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& summarize_model_line_41_3b22d89c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_export_bridge",
        "src/core/export/unity_export_bridge.py",
        "summarize_model",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_export_bridge","python_file":"src/core/export/unity_export_bridge.py","qualname":"summarize_model","name":"summarize_model","callable_type":"module_functions","line":41,"end_line":82,"signature":{"args":["model","game","resref","asset_path","unity_project","source_path"],"positional_count":5,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& inspect_fbx_skin_objects_line_85_bdc78f34_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_export_bridge",
        "src/core/export/unity_export_bridge.py",
        "inspect_fbx_skin_objects",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_export_bridge","python_file":"src/core/export/unity_export_bridge.py","qualname":"inspect_fbx_skin_objects","name":"inspect_fbx_skin_objects","callable_type":"module_functions","line":85,"end_line":156,"signature":{"args":["asset_path"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& export_model_for_unity_line_159_63d8706b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_export_bridge",
        "src/core/export/unity_export_bridge.py",
        "export_model_for_unity",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_export_bridge","python_file":"src/core/export/unity_export_bridge.py","qualname":"export_model_for_unity","name":"export_model_for_unity","callable_type":"module_functions","line":159,"end_line":203,"signature":{"args":["model","game","resref","asset_name","unity_project","asset_subdir","extension","export_rigging","exporter","source_path"],"positional_count":1,"keyword_only_count":9,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& as_list_line_10_902fc7b4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_import_validator",
        "src/core/export/unity_import_validator.py",
        "_as_list",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_import_validator","python_file":"src/core/export/unity_import_validator.py","qualname":"_as_list","name":"_as_list","callable_type":"module_functions","line":10,"end_line":17,"signature":{"args":["value"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& clip_name_line_20_8f3b8c4f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_import_validator",
        "src/core/export/unity_import_validator.py",
        "_clip_name",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_import_validator","python_file":"src/core/export/unity_import_validator.py","qualname":"_clip_name","name":"_clip_name","callable_type":"module_functions","line":20,"end_line":25,"signature":{"args":["item"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& renderer_type_line_28_e82cbec7_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_import_validator",
        "src/core/export/unity_import_validator.py",
        "_renderer_type",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_import_validator","python_file":"src/core/export/unity_import_validator.py","qualname":"_renderer_type","name":"_renderer_type","callable_type":"module_functions","line":28,"end_line":33,"signature":{"args":["item"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& renderer_int_line_36_b33aab39_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_import_validator",
        "src/core/export/unity_import_validator.py",
        "_renderer_int",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_import_validator","python_file":"src/core/export/unity_import_validator.py","qualname":"_renderer_int","name":"_renderer_int","callable_type":"module_functions","line":36,"end_line":45,"signature":{"args":["item","key"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& material_count_line_48_9d6865dc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_import_validator",
        "src/core/export/unity_import_validator.py",
        "_material_count",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_import_validator","python_file":"src/core/export/unity_import_validator.py","qualname":"_material_count","name":"_material_count","callable_type":"module_functions","line":48,"end_line":58,"signature":{"args":["unity_summary","renderers"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& build_unity_import_manifest_line_61_0bc29d4a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_import_validator",
        "src/core/export/unity_import_validator.py",
        "build_unity_import_manifest",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_import_validator","python_file":"src/core/export/unity_import_validator.py","qualname":"build_unity_import_manifest","name":"build_unity_import_manifest","callable_type":"module_functions","line":61,"end_line":177,"signature":{"args":["transfer_metadata","unity_summary"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& validate_unity_import_file_line_180_e7e3ce03_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Export",
        "ghostrigger::core::export_::core::export_::unity_import_validator",
        "src/core/export/unity_import_validator.py",
        "validate_unity_import_file",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Export","namespace":"ghostrigger::core::export_::core::export_::unity_import_validator","python_file":"src/core/export/unity_import_validator.py","qualname":"validate_unity_import_file","name":"validate_unity_import_file","callable_type":"module_functions","line":180,"end_line":193,"signature":{"args":["transfer_metadata_path","unity_summary","output_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        run_export_job_line_108_e68b41e9_native(),
        preflight_export_request_line_263_01b4bba5_native(),
        validate_staged_outputs_line_319_8e66a640_native(),
        result_line_334_e9ef6bd5_native(),
        single_issue_report_line_362_5757b4ff_native(),
        issue_line_385_4db8c74f_native(),
        publish_line_401_a53a92e7_native(),
        shared_output_parent_line_413_001c658b_native(),
        rollback_promoted_outputs_line_422_6cf28be4_native(),
        final_manifest_path_line_439_188f8463_native(),
        normalized_path_key_line_446_7fbdeaec_native(),
        safe_job_id_line_450_e73ab220_native(),
        ensure_json_serializable_line_455_dc882db9_native(),
        decode_accessor_line_152_6f438c5e_native(),
        resolve_buffers_line_231_3b6565af_native(),
        matrix_to_trs_line_265_79964a2c_native(),
        node_trs_from_mapping_line_318_b07a17f5_native(),
        node_scale_from_mapping_line_333_5454ffdb_native(),
        node_trs_from_object_line_346_bdd95aaa_native(),
        node_scale_from_object_line_361_ddbf387c_native(),
        mul_scale_line_369_72dca566_native(),
        apply_scale_to_pos_line_376_1219d937_native(),
        compose_gltf_world_line_383_c0f9e7e1_native(),
        gltf_root_indices_line_400_1b3f99ac_native(),
        candidate_blender_executables_line_1082_aaa33477_native(),
        blender_sort_key_line_1125_18a02b8a_native(),
        convert_fbx_to_glb_with_blender_line_1136_428ff1fd_native(),
        auto_import_line_1184_b404afc0_native(),
        build_skin_data_line_1215_fcd8f9f0_native(),
        channel_to_controller_line_1238_6e25f4a7_native(),
        fill_material_pygltflib_line_1258_6367fccf_native(),
        asset_relative_line_18_5ce50433_native(),
        build_output_paths_line_27_18384c92_native(),
        summarize_model_line_41_3b22d89c_native(),
        inspect_fbx_skin_objects_line_85_bdc78f34_native(),
        export_model_for_unity_line_159_63d8706b_native(),
        as_list_line_10_902fc7b4_native(),
        clip_name_line_20_8f3b8c4f_native(),
        renderer_type_line_28_e82cbec7_native(),
        renderer_int_line_36_b33aab39_native(),
        material_count_line_48_9d6865dc_native(),
        build_unity_import_manifest_line_61_0bc29d4a_native(),
        validate_unity_import_file_line_180_e7e3ce03_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::export_
