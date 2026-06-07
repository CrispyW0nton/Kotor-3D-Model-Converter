#pragma once

#include <cstddef>

namespace ghostrigger::gui::dialogs {

#ifndef GHOSTRIGGER_GUI_DIALOGS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_DIALOGS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_DIALOGS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& show_about_line_384_8da757ad_native();
const NativeFunctionImplementation& show_format_reference_line_396_c754379d_native();
const NativeFunctionImplementation& show_viewport_navigation_reference_line_404_e88fda60_native();
const NativeFunctionImplementation& show_ipc_info_line_412_046b12a9_native();
const NativeFunctionImplementation& wgpu_backend_type_line_41_084a96fb_native();
const NativeFunctionImplementation& load_settings_line_747_44c82cc7_native();
const NativeFunctionImplementation& save_settings_line_756_1a1ccaf9_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::dialogs
