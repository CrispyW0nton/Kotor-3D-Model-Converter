#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_windows_leveleditor {

const char* src_gui_windows_module_editor_window_moduleeditorwindow_project_line_64_2e88ed80_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Windows.LevelEditor","python_module":"src.gui.windows.module_editor_window","python_file":"src/gui/windows/module_editor_window.py","qualname":"ModuleEditorWindow.project","name":"project","kind":"properties","line":64,"end_line":65,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/windows/module_editor_window.py", "ModuleEditorWindow.project", "properties", &src_gui_windows_module_editor_window_moduleeditorwindow_project_line_64_2e88ed80_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_windows_leveleditor
