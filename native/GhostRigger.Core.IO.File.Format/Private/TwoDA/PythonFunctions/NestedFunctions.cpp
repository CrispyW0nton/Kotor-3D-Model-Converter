#include "2DA/PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::templates {

const NativeFunctionImplementation& twoda_parse_binary_get_str_line_175_54443ef9_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.IO.File.Format",
        "ghostrigger::core::templates::core::templates::twoda",
        "src/core/templates/twoda.py",
        "2DA._parse_binary.get_str",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.IO.File.Format","namespace":"ghostrigger::core::templates::core::templates::twoda","python_file":"src/core/templates/twoda.py","qualname":"2DA._parse_binary.get_str","name":"get_str","callable_type":"nested_functions","line":175,"end_line":182,"signature":{"args":["offset"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        twoda_parse_binary_get_str_line_175_54443ef9_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::templates
