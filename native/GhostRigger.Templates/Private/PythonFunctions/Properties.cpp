#include "PythonFunctions/Properties.h"

namespace ghostrigger::templates {

const NativeFunctionImplementation& twodarow_index_line_40_53831d48_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Templates",
        "ghostrigger::templates::core::templates::twoda",
        "src/core/templates/twoda.py",
        "TwoDARow.index",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Templates","namespace":"ghostrigger::templates::core::templates::twoda","python_file":"src/core/templates/twoda.py","qualname":"TwoDARow.index","name":"index","callable_type":"properties","line":40,"end_line":41,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        twodarow_index_line_40_53831d48_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::templates
