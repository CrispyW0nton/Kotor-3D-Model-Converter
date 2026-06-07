#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_gui_dialogs {

const char* src_gui_dialogs_add_model_to_scene_dialog_addmodeltoscenedialog_remember_choice_line_81_fd2c0ca3_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Dialogs","python_module":"src.gui.dialogs.add_model_to_scene_dialog","python_file":"src/gui/dialogs/add_model_to_scene_dialog.py","qualname":"AddModelToSceneDialog.remember_choice","name":"remember_choice","kind":"properties","line":81,"end_line":82,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_gui_dialogs_add_model_to_scene_dialog_addmodeltoscenedialog_placement_mode_line_85_6874109e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Dialogs","python_module":"src.gui.dialogs.add_model_to_scene_dialog","python_file":"src/gui/dialogs/add_model_to_scene_dialog.py","qualname":"AddModelToSceneDialog.placement_mode","name":"placement_mode","kind":"properties","line":85,"end_line":86,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/dialogs/add_model_to_scene_dialog.py", "AddModelToSceneDialog.remember_choice", "properties", &src_gui_dialogs_add_model_to_scene_dialog_addmodeltoscenedialog_remember_choice_line_81_fd2c0ca3_descriptor_json},
        {"src/gui/dialogs/add_model_to_scene_dialog.py", "AddModelToSceneDialog.placement_mode", "properties", &src_gui_dialogs_add_model_to_scene_dialog_addmodeltoscenedialog_placement_mode_line_85_6874109e_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_dialogs
