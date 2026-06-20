#include "PythonFunctions/Properties.h"

namespace ghostrigger::core::kotormcp {

const NativeFunctionImplementation& debugsession_uptime_s_line_119_caf797cb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Automation.MCP",
        "ghostrigger::core::kotormcp::tools::debug_skinning",
        "src/kotormcp/tools/debug_skinning.py",
        "_DebugSession.uptime_s",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Automation.MCP","namespace":"ghostrigger::core::kotormcp::tools::debug_skinning","python_file":"src/kotormcp/tools/debug_skinning.py","qualname":"_DebugSession.uptime_s","name":"uptime_s","callable_type":"properties","line":119,"end_line":122,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& resourceentryproxy_data_line_180_7da55bff_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Automation.MCP",
        "ghostrigger::core::kotormcp::tools::discovery",
        "src/kotormcp/tools/discovery.py",
        "_ResourceEntryProxy.data",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Automation.MCP","namespace":"ghostrigger::core::kotormcp::tools::discovery","python_file":"src/kotormcp/tools/discovery.py","qualname":"_ResourceEntryProxy.data","name":"data","callable_type":"properties","line":180,"end_line":181,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        debugsession_uptime_s_line_119_caf797cb_native(),
        resourceentryproxy_data_line_180_7da55bff_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::kotormcp
