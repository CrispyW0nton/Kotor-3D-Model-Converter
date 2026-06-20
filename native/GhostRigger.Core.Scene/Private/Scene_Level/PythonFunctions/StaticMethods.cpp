#include "Scene_Level/PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::level {

const NativeFunctionImplementation& kmapvalidator_valid_transform_line_123_f2f62e68_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Scene",
        "ghostrigger::core::level::core::level::kmap_validator",
        "src/core/level/kmap_validator.py",
        "KMapValidator._valid_transform",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Scene","namespace":"ghostrigger::core::level::core::level::kmap_validator","python_file":"src/core/level/kmap_validator.py","qualname":"KMapValidator._valid_transform","name":"_valid_transform","callable_type":"static_methods","line":123,"end_line":125,"signature":{"args":["transform"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& levelexportbridge_single_export_model_line_106_74e418b1_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Scene",
        "ghostrigger::core::level::core::level::level_export_bridge",
        "src/core/level/level_export_bridge.py",
        "LevelExportBridge._single_export_model",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Scene","namespace":"ghostrigger::core::level::core::level::level_export_bridge","python_file":"src/core/level/level_export_bridge.py","qualname":"LevelExportBridge._single_export_model","name":"_single_export_model","callable_type":"static_methods","line":106,"end_line":109,"signature":{"args":["project"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        kmapvalidator_valid_transform_line_123_f2f62e68_native(),
        levelexportbridge_single_export_model_line_106_74e418b1_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::level
