#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::camera {

#ifndef GHOSTRIGGER_GUI_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& getattr_line_19_bd15a5bb_native();
const NativeFunctionImplementation& dir_line_28_8f929c2b_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::camera
