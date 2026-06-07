#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_gui_panels {

const char* src_gui_panels_qt_content_browser_panel_contentassetdescriptor_searchable_text_line_403_b686721a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Panels","python_module":"src.gui.panels.qt_content_browser_panel","python_file":"src/gui/panels/qt_content_browser_panel.py","qualname":"ContentAssetDescriptor.searchable_text","name":"searchable_text","kind":"properties","line":403,"end_line":414,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_gui_panels_qt_rig_panel_qtrigwindow_status_label_line_177_c870d04c_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Panels","python_module":"src.gui.panels.qt_rig_panel","python_file":"src/gui/panels/qt_rig_panel.py","qualname":"QtRigWindow.status_label","name":"status_label","kind":"properties","line":177,"end_line":178,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/panels/qt_content_browser_panel.py", "ContentAssetDescriptor.searchable_text", "properties", &src_gui_panels_qt_content_browser_panel_contentassetdescriptor_searchable_text_line_403_b686721a_descriptor_json},
        {"src/gui/panels/qt_rig_panel.py", "QtRigWindow.status_label", "properties", &src_gui_panels_qt_rig_panel_qtrigwindow_status_label_line_177_c870d04c_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_panels
