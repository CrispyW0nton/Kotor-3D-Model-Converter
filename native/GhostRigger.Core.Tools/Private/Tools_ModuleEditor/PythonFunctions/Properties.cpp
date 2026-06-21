#include "Tools_ModuleEditor/PythonFunctions/Properties.h"

namespace ghostrigger::core::tools::moduleeditor {

const NativeFunctionImplementation& moduleeditorwindow_project_line_64_2e88ed80_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools",
        "ghostrigger::core::tools::moduleeditor::gui::windows::module_editor_window",
        "src/gui/windows/module_editor_window.py",
        "ModuleEditorWindow.project",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools","namespace":"ghostrigger::core::tools::moduleeditor::gui::windows::module_editor_window","python_file":"src/gui/windows/module_editor_window.py","qualname":"ModuleEditorWindow.project","name":"project","callable_type":"properties","line":64,"end_line":65,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        moduleeditorwindow_project_line_64_2e88ed80_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::tools::moduleeditor
