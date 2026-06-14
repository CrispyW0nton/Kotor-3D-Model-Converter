#pragma once

#include <cstddef>

namespace ghostrigger::gui::boundary::integration {

#ifndef GHOSTRIGGER_GUI_INTEGRATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_INTEGRATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_INTEGRATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& qtmatrixpanel_normalize_crop_line_149_67abe9b7_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::boundary::integration
