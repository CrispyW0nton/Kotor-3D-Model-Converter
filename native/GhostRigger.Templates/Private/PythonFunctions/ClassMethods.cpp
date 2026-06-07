#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::templates {

const NativeFunctionImplementation& twoda_from_bytes_line_88_45af8178_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Templates",
        "ghostrigger::templates::core::templates::twoda",
        "src/core/templates/twoda.py",
        "TwoDA.from_bytes",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Templates","namespace":"ghostrigger::templates::core::templates::twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA.from_bytes","name":"from_bytes","callable_type":"class_methods","line":88,"end_line":100,"signature":{"args":["cls","data","name"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& twoda_from_file_line_103_aca436e4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Templates",
        "ghostrigger::templates::core::templates::twoda",
        "src/core/templates/twoda.py",
        "TwoDA.from_file",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Templates","namespace":"ghostrigger::templates::core::templates::twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA.from_file","name":"from_file","callable_type":"class_methods","line":103,"end_line":109,"signature":{"args":["cls","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& twoda_parse_binary_line_114_bc648710_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Templates",
        "ghostrigger::templates::core::templates::twoda",
        "src/core/templates/twoda.py",
        "TwoDA._parse_binary",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Templates","namespace":"ghostrigger::templates::core::templates::twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA._parse_binary","name":"_parse_binary","callable_type":"class_methods","line":114,"end_line":195,"signature":{"args":["cls","data","name"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& twoda_parse_ascii_line_200_d1371498_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Templates",
        "ghostrigger::templates::core::templates::twoda",
        "src/core/templates/twoda.py",
        "TwoDA._parse_ascii",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Templates","namespace":"ghostrigger::templates::core::templates::twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDA._parse_ascii","name":"_parse_ascii","callable_type":"class_methods","line":200,"end_line":237,"signature":{"args":["cls","data","name"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        twoda_from_bytes_line_88_45af8178_native(),
        twoda_from_file_line_103_aca436e4_native(),
        twoda_parse_binary_line_114_bc648710_native(),
        twoda_parse_ascii_line_200_d1371498_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::templates
