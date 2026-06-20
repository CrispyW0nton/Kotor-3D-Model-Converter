#pragma once

#include <cstddef>

namespace ghostrigger::core::mdl {

#ifndef GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& mdlbinaryparser_from_files_line_74_5167f1ce_native();
const NativeFunctionImplementation& mdlbinaryparser_parse_files_line_85_cd15af6e_native();
const NativeFunctionImplementation& mdlbinarywriter_ensure_export_orientation_controller_line_1723_b0eb1123_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::mdl
