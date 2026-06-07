#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::formats {

const NativeFunctionImplementation& read_gff_line_271_ba45cf01_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Formats",
        "ghostrigger::formats::gff_reader",
        "src/formats/gff_reader.py",
        "read_gff",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Formats","namespace":"ghostrigger::formats::gff_reader","python_file":"src/formats/gff_reader.py","qualname":"read_gff","name":"read_gff","callable_type":"module_functions","line":271,"end_line":273,"signature":{"args":["data"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& write_gff_line_306_9e3facfa_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Formats",
        "ghostrigger::formats::gff_writer",
        "src/formats/gff_writer.py",
        "write_gff",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Formats","namespace":"ghostrigger::formats::gff_writer","python_file":"src/formats/gff_writer.py","qualname":"write_gff","name":"write_gff","callable_type":"module_functions","line":306,"end_line":308,"signature":{"args":["gff"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        read_gff_line_271_ba45cf01_native(),
        write_gff_line_306_9e3facfa_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::formats
