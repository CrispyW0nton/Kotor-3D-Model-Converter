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

const NativeFunctionImplementation& lipkeyframe_lt_line_131_797259dd_native();
const NativeFunctionImplementation& lipfile_to_bytes_line_198_9f8d9982_native();
const NativeFunctionImplementation& lipfile_to_file_line_213_b84e77e2_native();
const NativeFunctionImplementation& lipfile_get_shapes_line_222_c8f91519_native();
const NativeFunctionImplementation& lipfile_get_shape_at_time_line_266_f9399635_native();
const NativeFunctionImplementation& lipfile_add_keyframe_line_276_f5b4312e_native();
const NativeFunctionImplementation& lipfile_remove_keyframe_line_284_deb1089d_native();
const NativeFunctionImplementation& lipfile_validate_line_295_e1e505cf_native();
const NativeFunctionImplementation& unitybridgeclient_request_line_37_cd7b03b9_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::special
