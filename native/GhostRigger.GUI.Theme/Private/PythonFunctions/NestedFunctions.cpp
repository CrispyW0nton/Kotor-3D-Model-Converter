#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::phase15::ghostrigger_gui_theme {

const char* src_gui_libtheme_theme_loader_themeloader_derive_missing_colors_fill_line_128_25656650_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.theme_loader","python_file":"src/gui/libtheme/theme_loader.py","qualname":"ThemeLoader._derive_missing_colors.fill","name":"fill","kind":"nested_functions","line":128,"end_line":130,"signature":{"args":["name","value"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_gui_libtheme_theme_watcher_themelayoutwatcher_start_handler_on_modified_line_32_1956a09d_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.theme_watcher","python_file":"src/gui/libtheme/theme_watcher.py","qualname":"ThemeLayoutWatcher.start.Handler.on_modified","name":"on_modified","kind":"nested_functions","line":32,"end_line":34,"signature":{"args":["self","event"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_gui_libtheme_theme_watcher_themelayoutwatcher_start_handler_on_created_line_36_31753562_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.theme_watcher","python_file":"src/gui/libtheme/theme_watcher.py","qualname":"ThemeLayoutWatcher.start.Handler.on_created","name":"on_created","kind":"nested_functions","line":36,"end_line":38,"signature":{"args":["self","event"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/libtheme/theme_loader.py", "ThemeLoader._derive_missing_colors.fill", "nested_functions", &src_gui_libtheme_theme_loader_themeloader_derive_missing_colors_fill_line_128_25656650_descriptor_json},
        {"src/gui/libtheme/theme_watcher.py", "ThemeLayoutWatcher.start.Handler.on_modified", "nested_functions", &src_gui_libtheme_theme_watcher_themelayoutwatcher_start_handler_on_modified_line_32_1956a09d_descriptor_json},
        {"src/gui/libtheme/theme_watcher.py", "ThemeLayoutWatcher.start.Handler.on_created", "nested_functions", &src_gui_libtheme_theme_watcher_themelayoutwatcher_start_handler_on_created_line_36_31753562_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_theme
