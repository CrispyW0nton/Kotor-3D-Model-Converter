#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::tools::properties {

const NativeFunctionImplementation& moduleeditorpropertiespanel_set_vector_line_85_4910d35b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools.Properties",
        "ghostrigger::core::tools::properties::gui::panels::module_editor::module_editor_properties",
        "src/gui/panels/module_editor/module_editor_properties.py",
        "ModuleEditorPropertiesPanel._set_vector",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools.Properties","namespace":"ghostrigger::core::tools::properties::gui::panels::module_editor::module_editor_properties","python_file":"src/gui/panels/module_editor/module_editor_properties.py","qualname":"ModuleEditorPropertiesPanel._set_vector","name":"_set_vector","callable_type":"static_methods","line":85,"end_line":87,"signature":{"args":["boxes","values"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        moduleeditorpropertiespanel_set_vector_line_85_4910d35b_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::tools::properties
