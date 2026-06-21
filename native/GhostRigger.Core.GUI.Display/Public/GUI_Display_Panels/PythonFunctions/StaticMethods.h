#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::panels {

#ifndef GHOSTRIGGER_GUI_PANELS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_PANELS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_PANELS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& moduleeditorpropertiespanel_set_vector_line_85_4910d35b_native();
const NativeFunctionImplementation& qtcharacterbuilderwindow_character_builder_theme_stylesheet_line_551_081c8327_native();
const NativeFunctionImplementation& qtcharacterbuilderwindow_option_field_line_1975_4be3154b_native();
const NativeFunctionImplementation& qtcharacterbuilderwindow_settings_line_4222_ff8074da_native();
const NativeFunctionImplementation& qtdiagnosticspanel_safe_list_line_112_2f271222_native();
const NativeFunctionImplementation& qtdiagnosticspanel_performance_report_lines_line_206_254a0745_native();
const NativeFunctionImplementation& qtdiagnosticspanel_bytes_with_mb_line_245_51acfcc8_native();
const NativeFunctionImplementation& qtmeshoperationoptionswidget_double_spin_line_63_b81f3fe3_native();
const NativeFunctionImplementation& qtmeshoperationoptionswidget_int_spin_line_72_60c5d659_native();
const NativeFunctionImplementation& qtmeshoperationoptionswidget_checked_box_line_79_cbfce570_native();
const NativeFunctionImplementation& qtue5rigexportpanel_artifact_summary_line_175_ab052981_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::panels
