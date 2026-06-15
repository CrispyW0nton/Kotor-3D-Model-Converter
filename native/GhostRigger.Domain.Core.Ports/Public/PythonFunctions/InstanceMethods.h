#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::ports {

#ifndef GHOSTRIGGER_PORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_PORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_PORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& filewriterport_write_bytes_line_13_386e4596_native();
const NativeFunctionImplementation& filewriterport_write_text_line_16_f4a4863f_native();
const NativeFunctionImplementation& scriptcompilerport_compile_script_line_27_6df94b86_native();
const NativeFunctionImplementation& texturedecoder_decode_texture_line_27_e83bd02c_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::ports
