#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::special {

#ifndef GHOSTRIGGER_SPECIAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SPECIAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_SPECIAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& is_attachment_hook_line_42_aaf21135_native();
const NativeFunctionImplementation& is_inner_geometry_name_line_88_1469e7cb_native();
const NativeFunctionImplementation& is_face_mesh_name_line_106_75f4c4cc_native();
const NativeFunctionImplementation& metadata_path_for_asset_line_68_e5901084_native();
const NativeFunctionImplementation& choose_preferred_clip_line_76_3e99eed7_native();
const NativeFunctionImplementation& flatten_hierarchy_line_86_c71ba23d_native();
const NativeFunctionImplementation& subtree_from_name_line_98_d891d4f3_native();
const NativeFunctionImplementation& component_types_line_105_547bed59_native();
const NativeFunctionImplementation& collect_malak_unity_summary_line_112_d384b1ec_native();
const NativeFunctionImplementation& wait_for_file_line_158_cdbc8279_native();
const NativeFunctionImplementation& compare_screenshots_line_170_d08bbfc8_native();
const NativeFunctionImplementation& run_malak_main_menu_smoke_line_214_b49b20be_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::special
