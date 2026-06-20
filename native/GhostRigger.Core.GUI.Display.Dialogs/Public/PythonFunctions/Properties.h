#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::dialogs {

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

const NativeFunctionImplementation& addmodeltoscenedialog_remember_choice_line_81_fd2c0ca3_native();
const NativeFunctionImplementation& addmodeltoscenedialog_placement_mode_line_85_6874109e_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::dialogs
