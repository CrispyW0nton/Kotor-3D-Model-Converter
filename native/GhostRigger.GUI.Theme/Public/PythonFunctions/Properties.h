#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_theme {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_libtheme_layout_manager_layoutmanager_packaged_layout_dir_line_35_1ddb6334_descriptor_json();
const char* src_gui_libtheme_layout_manager_layoutmanager_user_layout_dir_line_39_752bcb64_descriptor_json();
const char* src_gui_libtheme_theme_manager_thememanager_packaged_theme_dir_line_47_189b0632_descriptor_json();
const char* src_gui_libtheme_theme_manager_thememanager_user_theme_dir_line_51_07b14327_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_theme
