#pragma once

#include <cstddef>

namespace ghostrigger::tools::twodabrowser {

#ifndef GHOSTRIGGER_TOOLS_TWODABROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_TWODABROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_TWODABROWSER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& gffreader_from_bytes_line_256_55910253_native();
const NativeFunctionImplementation& twoda_from_bytes_line_88_45af8178_native();
const NativeFunctionImplementation& twoda_from_file_line_103_aca436e4_native();
const NativeFunctionImplementation& twoda_parse_binary_line_114_bc648710_native();
const NativeFunctionImplementation& twoda_parse_ascii_line_200_d1371498_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::twodabrowser
