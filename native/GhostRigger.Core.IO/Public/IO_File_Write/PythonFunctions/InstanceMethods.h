#pragma once

#include <cstddef>

namespace ghostrigger::core::io::files {

#ifndef GHOSTRIGGER_CORE_IO_FILES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_CORE_IO_FILES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_CORE_IO_FILES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& localfilewriter_write_bytes_line_15_ad2c205d_native();
const NativeFunctionImplementation& localfilewriter_write_text_line_20_ec441b06_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::io::files
