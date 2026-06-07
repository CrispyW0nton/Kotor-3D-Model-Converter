#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::formats {

const NativeFunctionImplementation& gffwriter_serialize_collect_line_59_1e5f42ee_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Formats",
        "ghostrigger::formats::gff_writer",
        "src/formats/gff_writer.py",
        "GffWriter.serialize._collect",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Formats","namespace":"ghostrigger::formats::gff_writer","python_file":"src/formats/gff_writer.py","qualname":"GffWriter.serialize._collect","name":"_collect","callable_type":"nested_functions","line":59,"end_line":75,"signature":{"args":["s"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gffwriter_serialize_collect_line_59_1e5f42ee_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::formats
