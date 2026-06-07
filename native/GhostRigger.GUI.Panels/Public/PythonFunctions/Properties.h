#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_panels {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_panels_qt_content_browser_panel_contentassetdescriptor_searchable_text_line_403_b686721a_descriptor_json();
const char* src_gui_panels_qt_rig_panel_qtrigwindow_status_label_line_177_c870d04c_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_panels
