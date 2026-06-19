#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::sceneinformation {

#ifndef GHOSTRIGGER_TOOLS_SCENEINFORMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_SCENEINFORMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_SCENEINFORMATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& frustum_update_from_matrix_plane_line_139_e5dad599_native();
const NativeFunctionImplementation& frustum_update_from_camera_plane_through_pos_line_198_93dc44e6_native();
const NativeFunctionImplementation& qtinspectorpanel_populate_preview_page_emit_attach_line_549_659529d3_native();
const NativeFunctionImplementation& qtinspectorpanel_set_skeleton_template_options_field_line_1031_d2726e75_native();
const NativeFunctionImplementation& qtinspectorpanel_populate_check_actor_page_emit_play_line_1199_a571dc67_native();
const NativeFunctionImplementation& qtinspectorpanel_populate_motions_page_emit_library_play_line_1396_3ba0872d_native();
const NativeFunctionImplementation& qtinspectorpanel_selected_fit_override_combo_value_line_2196_d1277435_native();
const NativeFunctionImplementation& qtinspectorpanel_set_import_fit_report_fmt_error_line_2378_c31444bf_native();
const NativeFunctionImplementation& qtsceneoutlinerpanel_expanded_item_keys_walk_line_299_d41db2af_native();
const NativeFunctionImplementation& qtsceneoutlinerpanel_restore_expanded_item_keys_walk_line_314_2bc3db2d_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::sceneinformation
