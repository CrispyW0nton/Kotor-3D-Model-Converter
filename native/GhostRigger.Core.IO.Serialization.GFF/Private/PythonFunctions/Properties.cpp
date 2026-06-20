#include "PythonFunctions/Properties.h"

namespace ghostrigger::core::io::serialization::gff {

const NativeFunctionImplementation& locstring_english_line_116_e2fec86f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.IO.Serialization.GFF",
        "ghostrigger::core::io::serialization::gff::gff_types",
        "src/formats/gff_types.py",
        "LocString.english",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.IO.Serialization.GFF","namespace":"ghostrigger::core::io::serialization::gff::gff_types","python_file":"src/formats/gff_types.py","qualname":"LocString.english","name":"english","callable_type":"properties","line":116,"end_line":117,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        locstring_english_line_116_e2fec86f_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::io::serialization::gff
