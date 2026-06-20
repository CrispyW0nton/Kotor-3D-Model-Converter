#include "GUI_Display_Panels/PythonFunctions/Properties.h"

namespace ghostrigger::core::gui::panels {

const NativeFunctionImplementation& contentassetdescriptor_searchable_text_line_403_b686721a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display",
        "ghostrigger::core::gui::panels::qt_content_browser_panel",
        "src/gui/panels/qt_content_browser_panel.py",
        "ContentAssetDescriptor.searchable_text",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display","namespace":"ghostrigger::core::gui::panels::qt_content_browser_panel","python_file":"src/gui/panels/qt_content_browser_panel.py","qualname":"ContentAssetDescriptor.searchable_text","name":"searchable_text","callable_type":"properties","line":403,"end_line":414,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& qtrigwindow_status_label_line_177_c870d04c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display",
        "ghostrigger::core::gui::panels::qt_rig_panel",
        "src/gui/panels/qt_rig_panel.py",
        "QtRigWindow.status_label",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display","namespace":"ghostrigger::core::gui::panels::qt_rig_panel","python_file":"src/gui/panels/qt_rig_panel.py","qualname":"QtRigWindow.status_label","name":"status_label","callable_type":"properties","line":177,"end_line":178,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        contentassetdescriptor_searchable_text_line_403_b686721a_native(),
        qtrigwindow_status_label_line_177_c870d04c_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::gui::panels
