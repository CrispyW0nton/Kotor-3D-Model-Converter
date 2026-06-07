#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_special {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_special_hooks_is_attachment_hook_line_42_aaf21135_descriptor_json();
const char* src_core_special_render_constants_is_inner_geometry_name_line_88_1469e7cb_descriptor_json();
const char* src_core_special_render_constants_is_face_mesh_name_line_106_75f4c4cc_descriptor_json();
const char* src_core_special_unity_malak_smoke_metadata_path_for_asset_line_68_e5901084_descriptor_json();
const char* src_core_special_unity_malak_smoke_choose_preferred_clip_line_76_3e99eed7_descriptor_json();
const char* src_core_special_unity_malak_smoke_flatten_hierarchy_line_86_c71ba23d_descriptor_json();
const char* src_core_special_unity_malak_smoke_subtree_from_name_line_98_d891d4f3_descriptor_json();
const char* src_core_special_unity_malak_smoke_component_types_line_105_547bed59_descriptor_json();
const char* src_core_special_unity_malak_smoke_collect_malak_unity_summary_line_112_d384b1ec_descriptor_json();
const char* src_core_special_unity_malak_smoke_wait_for_file_line_158_cdbc8279_descriptor_json();
const char* src_core_special_unity_malak_smoke_compare_screenshots_line_170_d08bbfc8_descriptor_json();
const char* src_core_special_unity_malak_smoke_run_malak_main_menu_smoke_line_214_b49b20be_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_special
