#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::modules {

const NativeFunctionImplementation& moduleeditorcontroller_blueprint_type_for_library_asset_line_165_6428786f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Modules",
        "ghostrigger::modules::core::modules::module_editor_controller",
        "src/core/modules/module_editor_controller.py",
        "ModuleEditorController._blueprint_type_for_library_asset",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Modules","namespace":"ghostrigger::modules::core::modules::module_editor_controller","python_file":"src/core/modules/module_editor_controller.py","qualname":"ModuleEditorController._blueprint_type_for_library_asset","name":"_blueprint_type_for_library_asset","callable_type":"static_methods","line":165,"end_line":178,"signature":{"args":["category","resref"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        moduleeditorcontroller_blueprint_type_for_library_asset_line_165_6428786f_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::modules
