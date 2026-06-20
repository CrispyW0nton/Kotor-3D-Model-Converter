#pragma once

#include <cstddef>

namespace ghostrigger::core::special {

#ifndef GHOSTRIGGER_SPECIAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SPECIAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_SPECIAL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& lipshape_label_line_82_0c06e812_native();
const NativeFunctionImplementation& lipshape_from_phoneme_line_98_4a5108b5_native();
const NativeFunctionImplementation& lipfile_from_bytes_line_155_70542997_native();
const NativeFunctionImplementation& lipfile_from_file_line_190_1a30d4ed_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::special
