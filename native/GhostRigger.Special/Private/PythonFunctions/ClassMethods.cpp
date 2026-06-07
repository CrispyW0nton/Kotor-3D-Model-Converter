#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::special {

const NativeFunctionImplementation& lipshape_label_line_82_0c06e812_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Special",
        "ghostrigger::special::core::special::lip_reader",
        "src/core/special/lip_reader.py",
        "LIPShape.label",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Special","namespace":"ghostrigger::special::core::special::lip_reader","python_file":"src/core/special/lip_reader.py","qualname":"LIPShape.label","name":"label","callable_type":"class_methods","line":82,"end_line":95,"signature":{"args":["cls","shape_id"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lipshape_from_phoneme_line_98_4a5108b5_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Special",
        "ghostrigger::special::core::special::lip_reader",
        "src/core/special/lip_reader.py",
        "LIPShape.from_phoneme",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Special","namespace":"ghostrigger::special::core::special::lip_reader","python_file":"src/core/special/lip_reader.py","qualname":"LIPShape.from_phoneme","name":"from_phoneme","callable_type":"class_methods","line":98,"end_line":117,"signature":{"args":["cls","phoneme"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lipfile_from_bytes_line_155_70542997_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Special",
        "ghostrigger::special::core::special::lip_reader",
        "src/core/special/lip_reader.py",
        "LIPFile.from_bytes",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Special","namespace":"ghostrigger::special::core::special::lip_reader","python_file":"src/core/special/lip_reader.py","qualname":"LIPFile.from_bytes","name":"from_bytes","callable_type":"class_methods","line":155,"end_line":187,"signature":{"args":["cls","data","source_path"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& lipfile_from_file_line_190_1a30d4ed_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Special",
        "ghostrigger::special::core::special::lip_reader",
        "src/core/special/lip_reader.py",
        "LIPFile.from_file",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Special","namespace":"ghostrigger::special::core::special::lip_reader","python_file":"src/core/special/lip_reader.py","qualname":"LIPFile.from_file","name":"from_file","callable_type":"class_methods","line":190,"end_line":194,"signature":{"args":["cls","path"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        lipshape_label_line_82_0c06e812_native(),
        lipshape_from_phoneme_line_98_4a5108b5_native(),
        lipfile_from_bytes_line_155_70542997_native(),
        lipfile_from_file_line_190_1a30d4ed_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::special
