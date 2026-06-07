#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_contentbrowser {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_windows_application_core_shared_resource_loading_resourceloadingmixin_module_group_anchor_lyt_position_line_634_d4352bba_descriptor_json();
const char* src_gui_windows_application_core_shared_resource_loading_resourceloadingmixin_runtime_model_child_count_line_727_2f2b8208_descriptor_json();
const char* src_gui_windows_application_core_shared_resource_loading_resourceloadingmixin_model_bounds_center_line_738_b02c98be_descriptor_json();
const char* src_gui_windows_application_core_shared_resource_loading_resourceloadingmixin_supports_animation_retarget_target_line_946_75ffa719_descriptor_json();
const char* src_gui_windows_application_core_shared_resource_loading_resourceloadingmixin_derive_wok_resrefs_line_971_d2ba6539_descriptor_json();
const char* src_resources_game_library_gamelibrary_detect_game_tag_line_815_80fc5b7b_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_contentbrowser
