#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_gui_theme {

const char* src_gui_libtheme_theme_applier_themeapplier_precache_stylesheets_line_77_c29937da_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.theme_applier","python_file":"src/gui/libtheme/theme_applier.py","qualname":"ThemeApplier.precache_stylesheets","name":"precache_stylesheets","kind":"class_methods","line":77,"end_line":112,"signature":{"args":["cls","themes"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_gui_libtheme_theme_settings_themelayoutsettings_from_settings_line_29_0c63c89b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.theme_settings","python_file":"src/gui/libtheme/theme_settings.py","qualname":"ThemeLayoutSettings.from_settings","name":"from_settings","kind":"class_methods","line":29,"end_line":48,"signature":{"args":["cls","settings"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/libtheme/theme_applier.py", "ThemeApplier.precache_stylesheets", "class_methods", &src_gui_libtheme_theme_applier_themeapplier_precache_stylesheets_line_77_c29937da_descriptor_json},
        {"src/gui/libtheme/theme_settings.py", "ThemeLayoutSettings.from_settings", "class_methods", &src_gui_libtheme_theme_settings_themelayoutsettings_from_settings_line_29_0c63c89b_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_theme
