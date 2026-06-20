#include "GUI_Display_Theme/PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::gui::theme {

const NativeFunctionImplementation& themeapplier_precache_stylesheets_line_77_c29937da_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display",
        "ghostrigger::core::gui::theme::libtheme::theme_applier",
        "src/gui/libtheme/theme_applier.py",
        "ThemeApplier.precache_stylesheets",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display","namespace":"ghostrigger::core::gui::theme::libtheme::theme_applier","python_file":"src/gui/libtheme/theme_applier.py","qualname":"ThemeApplier.precache_stylesheets","name":"precache_stylesheets","callable_type":"class_methods","line":77,"end_line":112,"signature":{"args":["cls","themes"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& themelayoutsettings_from_settings_line_29_0c63c89b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display",
        "ghostrigger::core::gui::theme::libtheme::theme_settings",
        "src/gui/libtheme/theme_settings.py",
        "ThemeLayoutSettings.from_settings",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display","namespace":"ghostrigger::core::gui::theme::libtheme::theme_settings","python_file":"src/gui/libtheme/theme_settings.py","qualname":"ThemeLayoutSettings.from_settings","name":"from_settings","callable_type":"class_methods","line":29,"end_line":48,"signature":{"args":["cls","settings"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        themeapplier_precache_stylesheets_line_77_c29937da_native(),
        themelayoutsettings_from_settings_line_29_0c63c89b_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::gui::theme
