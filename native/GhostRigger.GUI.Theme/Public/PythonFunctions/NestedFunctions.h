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

const char* src_gui_libtheme_theme_loader_themeloader_derive_missing_colors_fill_line_128_25656650_descriptor_json();
const char* src_gui_libtheme_theme_watcher_themelayoutwatcher_start_handler_on_modified_line_32_1956a09d_descriptor_json();
const char* src_gui_libtheme_theme_watcher_themelayoutwatcher_start_handler_on_created_line_36_31753562_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_theme
