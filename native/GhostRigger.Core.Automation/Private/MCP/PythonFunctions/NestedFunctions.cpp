#include "MCP/PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::kotormcp {

const NativeFunctionImplementation& debugsession_load_model_depth_line_288_7527285a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Automation.vcxproj",
        "ghostrigger::core::kotormcp::tools::debug_skinning",
        "src/kotormcp/tools/debug_skinning.py",
        "_DebugSession.load_model._depth",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Automation.vcxproj","namespace":"ghostrigger::core::kotormcp::tools::debug_skinning","python_file":"src/kotormcp/tools/debug_skinning.py","qualname":"_DebugSession.load_model._depth","name":"_depth","callable_type":"nested_functions","line":288,"end_line":292,"signature":{"args":["nd","d"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& debugsession_get_bone_hierarchy_build_tree_line_606_3daacf2b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Automation.vcxproj",
        "ghostrigger::core::kotormcp::tools::debug_skinning",
        "src/kotormcp/tools/debug_skinning.py",
        "_DebugSession.get_bone_hierarchy._build_tree",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Automation.vcxproj","namespace":"ghostrigger::core::kotormcp::tools::debug_skinning","python_file":"src/kotormcp/tools/debug_skinning.py","qualname":"_DebugSession.get_bone_hierarchy._build_tree","name":"_build_tree","callable_type":"nested_functions","line":606,"end_line":616,"signature":{"args":["node","depth"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& close_quat_close_line_104_b36abb8a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Automation.vcxproj",
        "ghostrigger::core::kotormcp::tools::ghostrigger_tools",
        "src/kotormcp/tools/ghostrigger_tools.py",
        "_close_quat.close",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Automation.vcxproj","namespace":"ghostrigger::core::kotormcp::tools::ghostrigger_tools","python_file":"src/kotormcp/tools/ghostrigger_tools.py","qualname":"_close_quat.close","name":"close","callable_type":"nested_functions","line":104,"end_line":105,"signature":{"args":["sign"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& compare_model_pipelines_add_line_261_5b32c5d1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Automation.vcxproj",
        "ghostrigger::core::kotormcp::tools::ghostrigger_tools",
        "src/kotormcp/tools/ghostrigger_tools.py",
        "compare_model_pipelines.add",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Automation.vcxproj","namespace":"ghostrigger::core::kotormcp::tools::ghostrigger_tools","python_file":"src/kotormcp/tools/ghostrigger_tools.py","qualname":"compare_model_pipelines.add","name":"add","callable_type":"nested_functions","line":261,"end_line":265,"signature":{"args":["field","pykotor","ghostrigger"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        debugsession_load_model_depth_line_288_7527285a_native(),
        debugsession_get_bone_hierarchy_build_tree_line_606_3daacf2b_native(),
        close_quat_close_line_104_b36abb8a_native(),
        compare_model_pipelines_add_line_261_5b32c5d1_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::kotormcp
