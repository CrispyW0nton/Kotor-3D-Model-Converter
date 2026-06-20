#include "GUI_Display_Theme/PythonFunctions/Properties.h"

namespace ghostrigger::core::gui::theme {

const NativeFunctionImplementation& layoutmanager_packaged_layout_dir_line_35_1ddb6334_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display",
        "ghostrigger::core::gui::theme::libtheme::layout_manager",
        "src/gui/libtheme/layout_manager.py",
        "LayoutManager.packaged_layout_dir",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display","namespace":"ghostrigger::core::gui::theme::libtheme::layout_manager","python_file":"src/gui/libtheme/layout_manager.py","qualname":"LayoutManager.packaged_layout_dir","name":"packaged_layout_dir","callable_type":"properties","line":35,"end_line":36,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& layoutmanager_user_layout_dir_line_39_752bcb64_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display",
        "ghostrigger::core::gui::theme::libtheme::layout_manager",
        "src/gui/libtheme/layout_manager.py",
        "LayoutManager.user_layout_dir",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display","namespace":"ghostrigger::core::gui::theme::libtheme::layout_manager","python_file":"src/gui/libtheme/layout_manager.py","qualname":"LayoutManager.user_layout_dir","name":"user_layout_dir","callable_type":"properties","line":39,"end_line":40,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& thememanager_packaged_theme_dir_line_47_189b0632_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display",
        "ghostrigger::core::gui::theme::libtheme::theme_manager",
        "src/gui/libtheme/theme_manager.py",
        "ThemeManager.packaged_theme_dir",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display","namespace":"ghostrigger::core::gui::theme::libtheme::theme_manager","python_file":"src/gui/libtheme/theme_manager.py","qualname":"ThemeManager.packaged_theme_dir","name":"packaged_theme_dir","callable_type":"properties","line":47,"end_line":48,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& thememanager_user_theme_dir_line_51_07b14327_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display",
        "ghostrigger::core::gui::theme::libtheme::theme_manager",
        "src/gui/libtheme/theme_manager.py",
        "ThemeManager.user_theme_dir",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display","namespace":"ghostrigger::core::gui::theme::libtheme::theme_manager","python_file":"src/gui/libtheme/theme_manager.py","qualname":"ThemeManager.user_theme_dir","name":"user_theme_dir","callable_type":"properties","line":51,"end_line":52,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        layoutmanager_packaged_layout_dir_line_35_1ddb6334_native(),
        layoutmanager_user_layout_dir_line_39_752bcb64_native(),
        thememanager_packaged_theme_dir_line_47_189b0632_native(),
        thememanager_user_theme_dir_line_51_07b14327_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::gui::theme
