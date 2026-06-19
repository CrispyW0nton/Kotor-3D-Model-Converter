#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::tools::characterbuilder {

const NativeFunctionImplementation& qtcharacterbuilderwindow_character_builder_theme_stylesheet_line_551_081c8327_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools.CharacterBuilder",
        "ghostrigger::core::tools::characterbuilder::gui::panels::qt_character_builder_panel",
        "src/gui/panels/qt_character_builder_panel.py",
        "QtCharacterBuilderWindow._character_builder_theme_stylesheet",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools.CharacterBuilder","namespace":"ghostrigger::core::tools::characterbuilder::gui::panels::qt_character_builder_panel","python_file":"src/gui/panels/qt_character_builder_panel.py","qualname":"QtCharacterBuilderWindow._character_builder_theme_stylesheet","name":"_character_builder_theme_stylesheet","callable_type":"static_methods","line":551,"end_line":692,"signature":{"args":["theme"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& qtcharacterbuilderwindow_option_field_line_1975_4be3154b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools.CharacterBuilder",
        "ghostrigger::core::tools::characterbuilder::gui::panels::qt_character_builder_panel",
        "src/gui/panels/qt_character_builder_panel.py",
        "QtCharacterBuilderWindow._option_field",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools.CharacterBuilder","namespace":"ghostrigger::core::tools::characterbuilder::gui::panels::qt_character_builder_panel","python_file":"src/gui/panels/qt_character_builder_panel.py","qualname":"QtCharacterBuilderWindow._option_field","name":"_option_field","callable_type":"static_methods","line":1975,"end_line":1978,"signature":{"args":["option","name","default"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& qtcharacterbuilderwindow_settings_line_4222_ff8074da_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools.CharacterBuilder",
        "ghostrigger::core::tools::characterbuilder::gui::panels::qt_character_builder_panel",
        "src/gui/panels/qt_character_builder_panel.py",
        "QtCharacterBuilderWindow._settings",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools.CharacterBuilder","namespace":"ghostrigger::core::tools::characterbuilder::gui::panels::qt_character_builder_panel","python_file":"src/gui/panels/qt_character_builder_panel.py","qualname":"QtCharacterBuilderWindow._settings","name":"_settings","callable_type":"static_methods","line":4222,"end_line":4223,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        qtcharacterbuilderwindow_character_builder_theme_stylesheet_line_551_081c8327_native(),
        qtcharacterbuilderwindow_option_field_line_1975_4be3154b_native(),
        qtcharacterbuilderwindow_settings_line_4222_ff8074da_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::tools::characterbuilder
