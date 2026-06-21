#include "Tools_BAS/PythonFunctions/Properties.h"

namespace ghostrigger::core::tools::bas {

const NativeFunctionImplementation& bodyguideedithistory_can_undo_line_3233_965ab5fb_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools",
        "ghostrigger::core::tools::bas::core::characters::headless_body_workflow",
        "src/core/characters/headless_body_workflow.py",
        "BodyGuideEditHistory.can_undo",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools","namespace":"ghostrigger::core::tools::bas::core::characters::headless_body_workflow","python_file":"src/core/characters/headless_body_workflow.py","qualname":"BodyGuideEditHistory.can_undo","name":"can_undo","callable_type":"properties","line":3233,"end_line":3234,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& bodyguideedithistory_can_redo_line_3237_68214687_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools",
        "ghostrigger::core::tools::bas::core::characters::headless_body_workflow",
        "src/core/characters/headless_body_workflow.py",
        "BodyGuideEditHistory.can_redo",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools","namespace":"ghostrigger::core::tools::bas::core::characters::headless_body_workflow","python_file":"src/core/characters/headless_body_workflow.py","qualname":"BodyGuideEditHistory.can_redo","name":"can_redo","callable_type":"properties","line":3237,"end_line":3238,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        bodyguideedithistory_can_undo_line_3233_965ab5fb_native(),
        bodyguideedithistory_can_redo_line_3237_68214687_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::tools::bas
