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

const char* src_gui_libtheme_theme_applier_themeapplier_precache_stylesheets_line_77_c29937da_descriptor_json();
const char* src_gui_libtheme_theme_settings_themelayoutsettings_from_settings_line_29_0c63c89b_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_theme
