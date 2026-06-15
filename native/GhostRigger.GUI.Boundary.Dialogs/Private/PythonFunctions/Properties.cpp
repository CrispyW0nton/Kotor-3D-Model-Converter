#include "PythonFunctions/Properties.h"

namespace ghostrigger::gui::boundary::dialogs {

const NativeFunctionImplementation& addmodeltoscenedialog_remember_choice_line_81_fd2c0ca3_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.GUI.Boundary.Dialogs",
        "ghostrigger::gui::boundary::dialogs::add_model_to_scene_dialog",
        "src/gui/dialogs/add_model_to_scene_dialog.py",
        "AddModelToSceneDialog.remember_choice",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.GUI.Boundary.Dialogs","namespace":"ghostrigger::gui::boundary::dialogs::add_model_to_scene_dialog","python_file":"src/gui/dialogs/add_model_to_scene_dialog.py","qualname":"AddModelToSceneDialog.remember_choice","name":"remember_choice","callable_type":"properties","line":81,"end_line":82,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& addmodeltoscenedialog_placement_mode_line_85_6874109e_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.GUI.Boundary.Dialogs",
        "ghostrigger::gui::boundary::dialogs::add_model_to_scene_dialog",
        "src/gui/dialogs/add_model_to_scene_dialog.py",
        "AddModelToSceneDialog.placement_mode",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.GUI.Boundary.Dialogs","namespace":"ghostrigger::gui::boundary::dialogs::add_model_to_scene_dialog","python_file":"src/gui/dialogs/add_model_to_scene_dialog.py","qualname":"AddModelToSceneDialog.placement_mode","name":"placement_mode","callable_type":"properties","line":85,"end_line":86,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        addmodeltoscenedialog_remember_choice_line_81_fd2c0ca3_native(),
        addmodeltoscenedialog_placement_mode_line_85_6874109e_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::gui::boundary::dialogs
