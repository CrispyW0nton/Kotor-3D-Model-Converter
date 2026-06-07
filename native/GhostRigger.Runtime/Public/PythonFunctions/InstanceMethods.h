#pragma once

#include <cstddef>

namespace ghostrigger::runtime {

#ifndef GHOSTRIGGER_RUNTIME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RUNTIME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RUNTIME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& aliasloader_construct_line_224_c5fe8728_native();
const NativeFunctionImplementation& aliasloader_create_module_line_227_75e53f13_native();
const NativeFunctionImplementation& aliasloader_exec_module_line_230_c94fed86_native();
const NativeFunctionImplementation& aliasfinder_find_spec_line_242_f27746af_native();
const NativeFunctionImplementation& lazymodule_construct_line_257_ddb72fa4_native();
const NativeFunctionImplementation& lazymodule_load_line_262_2256a9af_native();
const NativeFunctionImplementation& lazymodule_getattr_line_272_e592785f_native();
const NativeFunctionImplementation& lazymodule_setattr_line_275_771d313f_native();
const NativeFunctionImplementation& lazymodule_delattr_line_282_8529e3e5_native();
const NativeFunctionImplementation& lazymodule_dir_line_289_97285489_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::runtime
