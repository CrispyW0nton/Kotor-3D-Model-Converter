#pragma once

#include <cstddef>

namespace ghostrigger::rendering {

#ifndef GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& hardwarediagnostics_from_dict_line_56_a66bccdf_native();
const NativeFunctionImplementation& renderercapabilities_from_dict_line_104_185dfd96_native();
const NativeFunctionImplementation& renderersettings_from_settings_line_68_2bcc02b5_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::rendering
