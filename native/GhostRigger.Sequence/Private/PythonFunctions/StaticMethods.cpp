#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::sequence {

const NativeFunctionImplementation& sequencemanager_safe_filename_line_174_6e8e07fc_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Sequence",
        "ghostrigger::sequence::sequence_manager",
        "src/sequence/sequence_manager.py",
        "SequenceManager.safe_filename",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Sequence","namespace":"ghostrigger::sequence::sequence_manager","python_file":"src/sequence/sequence_manager.py","qualname":"SequenceManager.safe_filename","name":"safe_filename","callable_type":"static_methods","line":174,"end_line":177,"signature":{"args":["name"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        sequencemanager_safe_filename_line_174_6e8e07fc_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::sequence
