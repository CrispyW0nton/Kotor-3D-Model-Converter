#pragma once

#include <cstddef>

namespace ghostrigger::tools::workflow::properties {

#ifndef GHOSTRIGGER_TOOLS_PROPERTIES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_PROPERTIES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_PROPERTIES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& qtinspectorpanel_populate_preview_page_emit_attach_line_549_659529d3_native();
const NativeFunctionImplementation& qtinspectorpanel_set_skeleton_template_options_field_line_1031_d2726e75_native();
const NativeFunctionImplementation& qtinspectorpanel_populate_check_actor_page_emit_play_line_1199_a571dc67_native();
const NativeFunctionImplementation& qtinspectorpanel_populate_motions_page_emit_library_play_line_1396_3ba0872d_native();
const NativeFunctionImplementation& qtinspectorpanel_selected_fit_override_combo_value_line_2196_d1277435_native();
const NativeFunctionImplementation& qtinspectorpanel_set_import_fit_report_fmt_error_line_2378_c31444bf_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::workflow::properties
