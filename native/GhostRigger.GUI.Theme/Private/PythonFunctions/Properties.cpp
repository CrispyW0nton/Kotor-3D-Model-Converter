#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_gui_theme {

const char* src_gui_libtheme_layout_manager_layoutmanager_packaged_layout_dir_line_35_1ddb6334_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.layout_manager","python_file":"src/gui/libtheme/layout_manager.py","qualname":"LayoutManager.packaged_layout_dir","name":"packaged_layout_dir","kind":"properties","line":35,"end_line":36,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_gui_libtheme_layout_manager_layoutmanager_user_layout_dir_line_39_752bcb64_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.layout_manager","python_file":"src/gui/libtheme/layout_manager.py","qualname":"LayoutManager.user_layout_dir","name":"user_layout_dir","kind":"properties","line":39,"end_line":40,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_gui_libtheme_theme_manager_thememanager_packaged_theme_dir_line_47_189b0632_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.theme_manager","python_file":"src/gui/libtheme/theme_manager.py","qualname":"ThemeManager.packaged_theme_dir","name":"packaged_theme_dir","kind":"properties","line":47,"end_line":48,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_gui_libtheme_theme_manager_thememanager_user_theme_dir_line_51_07b14327_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.GUI.Theme","python_module":"src.gui.libtheme.theme_manager","python_file":"src/gui/libtheme/theme_manager.py","qualname":"ThemeManager.user_theme_dir","name":"user_theme_dir","kind":"properties","line":51,"end_line":52,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/gui/libtheme/layout_manager.py", "LayoutManager.packaged_layout_dir", "properties", &src_gui_libtheme_layout_manager_layoutmanager_packaged_layout_dir_line_35_1ddb6334_descriptor_json},
        {"src/gui/libtheme/layout_manager.py", "LayoutManager.user_layout_dir", "properties", &src_gui_libtheme_layout_manager_layoutmanager_user_layout_dir_line_39_752bcb64_descriptor_json},
        {"src/gui/libtheme/theme_manager.py", "ThemeManager.packaged_theme_dir", "properties", &src_gui_libtheme_theme_manager_thememanager_packaged_theme_dir_line_47_189b0632_descriptor_json},
        {"src/gui/libtheme/theme_manager.py", "ThemeManager.user_theme_dir", "properties", &src_gui_libtheme_theme_manager_thememanager_user_theme_dir_line_51_07b14327_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_gui_theme
