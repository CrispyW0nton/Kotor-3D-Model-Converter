#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::gui::theme {

const NativeFunctionImplementation& themeloader_derive_missing_colors_fill_line_128_25656650_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display.Theme",
        "ghostrigger::core::gui::theme::libtheme::theme_loader",
        "src/gui/libtheme/theme_loader.py",
        "ThemeLoader._derive_missing_colors.fill",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display.Theme","namespace":"ghostrigger::core::gui::theme::libtheme::theme_loader","python_file":"src/gui/libtheme/theme_loader.py","qualname":"ThemeLoader._derive_missing_colors.fill","name":"fill","callable_type":"nested_functions","line":128,"end_line":130,"signature":{"args":["name","value"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& themelayoutwatcher_start_handler_on_modified_line_32_1956a09d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display.Theme",
        "ghostrigger::core::gui::theme::libtheme::theme_watcher",
        "src/gui/libtheme/theme_watcher.py",
        "ThemeLayoutWatcher.start.Handler.on_modified",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display.Theme","namespace":"ghostrigger::core::gui::theme::libtheme::theme_watcher","python_file":"src/gui/libtheme/theme_watcher.py","qualname":"ThemeLayoutWatcher.start.Handler.on_modified","name":"on_modified","callable_type":"nested_functions","line":32,"end_line":34,"signature":{"args":["self","event"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& themelayoutwatcher_start_handler_on_created_line_36_31753562_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.GUI.Display.Theme",
        "ghostrigger::core::gui::theme::libtheme::theme_watcher",
        "src/gui/libtheme/theme_watcher.py",
        "ThemeLayoutWatcher.start.Handler.on_created",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.GUI.Display.Theme","namespace":"ghostrigger::core::gui::theme::libtheme::theme_watcher","python_file":"src/gui/libtheme/theme_watcher.py","qualname":"ThemeLayoutWatcher.start.Handler.on_created","name":"on_created","callable_type":"nested_functions","line":36,"end_line":38,"signature":{"args":["self","event"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        themeloader_derive_missing_colors_fill_line_128_25656650_native(),
        themelayoutwatcher_start_handler_on_modified_line_32_1956a09d_native(),
        themelayoutwatcher_start_handler_on_created_line_36_31753562_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::gui::theme
