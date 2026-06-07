#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_windows_unrealanimatorwindow {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_node_name_key_line_785_481bc949_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_is_descendant_line_843_54428b4d_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_is_source_null_helper_node_line_869_a373cec2_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_is_source_null_helper_name_line_874_39a297a0_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_node_world_position_line_879_82e27047_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_set_viewport_gpu_enabled_line_1046_75731430_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_source_bone_role_line_1392_11e13bdc_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_windows_unrealanimatorwindow
