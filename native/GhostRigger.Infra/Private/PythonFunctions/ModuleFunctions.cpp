#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::infra {

const NativeFunctionImplementation& maybe_autostart_kotormcp_line_17_3a73802a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Infra",
        "ghostrigger::infra::mcp_autostart",
        "src/infra/mcp_autostart.py",
        "maybe_autostart_kotormcp",
        "module_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Infra","namespace":"ghostrigger::infra::mcp_autostart","python_file":"src/infra/mcp_autostart.py","qualname":"maybe_autostart_kotormcp","name":"maybe_autostart_kotormcp","callable_type":"module_functions","line":17,"end_line":90,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        maybe_autostart_kotormcp_line_17_3a73802a_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::infra
