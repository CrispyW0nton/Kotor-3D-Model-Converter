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

const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_should_synthesize_quinn_bridge_bone_line_690_77764356_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_nearest_mapped_target_ancestor_line_698_37c74f8e_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_target_chain_between_line_712_6896e5a8_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_can_thread_bridge_between_source_nodes_line_729_d788a09f_descriptor_json();
const char* src_gui_windows_qt_unreal_animator_qtunrealanimatorwindow_can_thread_source_spine_line_857_a205a42a_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_windows_unrealanimatorwindow
