#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_properties {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_panels_qt_inspector_panel_qtinspectorpanel_populate_preview_page_emit_attach_line_549_659529d3_descriptor_json();
const char* src_gui_panels_qt_inspector_panel_qtinspectorpanel_set_skeleton_template_options_field_line_1031_d2726e75_descriptor_json();
const char* src_gui_panels_qt_inspector_panel_qtinspectorpanel_populate_check_actor_page_emit_play_line_1199_a571dc67_descriptor_json();
const char* src_gui_panels_qt_inspector_panel_qtinspectorpanel_populate_motions_page_emit_library_play_line_1396_3ba0872d_descriptor_json();
const char* src_gui_panels_qt_inspector_panel_qtinspectorpanel_selected_fit_override_combo_value_line_2196_d1277435_descriptor_json();
const char* src_gui_panels_qt_inspector_panel_qtinspectorpanel_set_import_fit_report_fmt_error_line_2378_c31444bf_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_properties
