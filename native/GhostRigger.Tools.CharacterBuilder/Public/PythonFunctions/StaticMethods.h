#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_characterbuilder {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_panels_qt_character_builder_panel_qtcharacterbuilderwindow_character_builder_theme_stylesheet_line_551_081c8327_descriptor_json();
const char* src_gui_panels_qt_character_builder_panel_qtcharacterbuilderwindow_option_field_line_1975_4be3154b_descriptor_json();
const char* src_gui_panels_qt_character_builder_panel_qtcharacterbuilderwindow_settings_line_4222_ff8074da_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_characterbuilder
